"""Real PC-P9 motor bench. Does not require or modify the Android phone."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import argparse, datetime, json, mimetypes, secrets, socket, sys, threading, time, re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(Path.home()/'Documents/ch32-tools/python-support'))
import serial
from serial.tools import list_ports
sys.path.insert(0,str(HERE))
from pc_integration import Integration

MECANUM_LAYOUTS = {
    'R1_DRIVE_STARTUP_MANUAL_MECANUM_V2_20261107': 'DRIVE_CHASSIS,MECANUM_X,FL_RL_FR_RR,250,600',
    'R1_DRIVE_STARTUP_MANUAL_MECANUM_V3_20261107': 'DRIVE_CHASSIS,MECANUM_GROUND_MAP,SWAP_M2_M4,250,600',
}


def integer(body, name, low, high):
    value = body.get(name)
    if type(value) is not int or not low <= value <= high:
        raise ValueError('参数超出范围：'+name)
    return value


class Bench:
    def __init__(self, output):
        self.lock = threading.Lock()
        self.quit = threading.Event()
        self.link = None
        self.owner = None
        self.control_verified = False
        self.identity = ''
        self.line_supported = False
        self.mpu_supported = False
        self.imu_observer_supported = False
        self.generation = self.seq = 0
        self.touched = 0
        self.latest = {'connected': False, 'error': '等待电脑连接开发板P9', 'sampled': 0}
        self.buffer = bytearray()
        self.raw = (output/'serial-http.jsonl').open('a', encoding='utf8', buffering=1)
        self.raw_lock = threading.Lock()
        self.integration = Integration(output)
        self.pending_command=None;self.last_link_failure=None

    def log(self, kind, **fields):
        with self.raw_lock:
            self.raw.write(json.dumps(dict(at=time.time(), kind=kind, **fields), ensure_ascii=False)+'\n')

    def exchange(self, command, prefix):
        self.pending_command=command
        packet = (command+'\n').encode('ascii')
        self.log('TX_ATTEMPT', hex=packet.hex())
        written = self.link.write(packet)
        if written != len(packet):
            raise OSError('串口指令未完整发送')
        self.log('TX', hex=packet.hex())
        readonly = command in ('DRIVE_ID','DRIVE_CAPS','DRIVE_STATUS','MOTOR_DASH_STATUS','DRIVE_DIAG','DRIVE_ACTUATORS','DRIVE_PROFILE','DRIVE_CHASSIS','DRIVE_VECTOR_STATUS')
        end = time.monotonic()+(1.5 if readonly else .45)
        while time.monotonic() < end:
            data = self.link.read(self.link.in_waiting or 1)
            if data:
                self.log('RX', hex=data.hex())
                self.buffer.extend(data)
            while b'\n' in self.buffer:
                row, _, tail = self.buffer.partition(b'\n')
                self.buffer[:] = tail
                text = row.decode('ascii', errors='replace').strip()
                if text.startswith(prefix):
                    return text
                if text.startswith(('ERR,', 'BENCH_RUN_BUSY', 'MOTOR_DISABLED')):
                    raise ValueError('主控拒绝：'+text)
        raise TimeoutError('主控回执超时：'+command.split(',')[0])

    def numbers(self, command, prefix, count):
        values = [int(v) for v in self.exchange(command, prefix).split(',')[1:]]
        if len(values) != count:
            raise ValueError('主控数据格式错误：'+command)
        return values

    def is_mecanum(self):
        return self.identity in MECANUM_LAYOUTS

    def snapshot(self):
        drive = self.numbers('DRIVE_STATUS', 'DRIVE,', 9)
        motor = self.numbers('MOTOR_DASH_STATUS', 'MOTORDASH,', 14)
        diag = self.numbers('DRIVE_DIAG', 'DRIVEDIAG,', 13)
        actuators = self.numbers('DRIVE_ACTUATORS','ACTUATORS,',10) if self.identity.startswith('R1_DRIVE_STARTUP') else None
        if self.owner and (not drive[1] or drive[3] != self.generation):
            self.owner = None
        self.latest = dict(connected=True, error='', sampled=time.monotonic(),
            firmware=self.identity, transport='电脑 → P9 → CH32',
            distance_mm=diag[2], blocked=diag[1], voltage_mv=motor[1] if motor[2] else None,
            wheel_speeds=motor[5:9] if motor[4] else None,
            motor_active=bool(motor[9]), motor_fault=motor[11], uart_errors=diag[9], uart_drops=diag[10],
            drive=dict(active=bool(drive[1]), moving=bool(drive[2]), left_pwm=drive[5], right_pwm=drive[6],
                       generation=drive[3], last_seq=drive[4], reason=drive[7]),
            raw=dict(drive=drive, motor=motor, diag=diag))
        if actuators:
            native=('MANUAL_V5' in self.identity or 'MANUAL_V6' in self.identity or ('MANUAL_V7' in self.identity or ('MANUAL_V8' in self.identity or self.is_mecanum())))
            self.latest.update(control_model='driver_native_speed' if native else 'wheel_speed',applied_pwm=None if native else actuators[1:5],speed_commands=actuators[1:5] if native else None,speed_targets=actuators[5:9],controller_fault=actuators[9])
        if ('MANUAL_V5' in self.identity or 'MANUAL_V6' in self.identity or ('MANUAL_V7' in self.identity or ('MANUAL_V8' in self.identity or self.is_mecanum()))):
            profile=self.numbers('DRIVE_PROFILE','DRIVE_PROFILE,',9)
            self.latest['driver_speed_limit']=1000 if ('MANUAL_V7' in self.identity or ('MANUAL_V8' in self.identity or self.is_mecanum())) else 120
            self.latest['driver_profile']=dict(zip(('ready','type','deadzone','lines','ratio','diameter_milli','p_milli','i_milli','d_milli'),profile))
        self.log('snapshot', data={k:v for k,v in self.latest.items() if k!='sampled'})

    def state(self):
        # A single dictionary replacement is atomic. Reads never wait behind serial IO.
        data = self.latest.copy()
        age = (time.monotonic()-data.pop('sampled'))*1000
        data['age_ms'] = round(age) if age < 86400000 else None
        if not data['connected'] or age > 1000:
            data.update(connected=False, voltage_mv=None, wheel_speeds=None)
        profile_ready=data.get('driver_profile',{'ready':1})['ready']==1
        reason=data.get('error') or ('本版四驱正在验收，暂未开放' if not self.control_verified else '等待电机驱动板供电与参数回报；请检查电池开关' if not profile_ready else '')
        data['capabilities'] = {'drive_control': data['connected'] and self.control_verified and profile_ready, 'drive_reason': reason}
        data['capabilities']['mecanum_control']=data['capabilities']['drive_control'] and self.is_mecanum()
        data.setdefault('drive',{})['chassis']='mecanum' if self.is_mecanum() else 'differential'
        data['demo'] = False
        data['last_link_failure']=self.last_link_failure
        return self.integration.enrich(data)

    def stop(self):
        self.owner = None
        self.exchange('DRIVE_STOP', 'DRIVE_STOPPED')
        self.exchange('MOTOR_STOP', 'MOTOR_STOP_QUEUED')
        self.snapshot()
        d = self.latest['drive']
        if d['active'] or d['left_pwm'] or d['right_pwm'] or self.latest['motor_active']:
            raise ValueError('尚未收到主控零目标确认')

    def command(self, action, body):
        deadline = time.monotonic()+.45
        if not self.lock.acquire(timeout=.35):
            raise ValueError('串口忙，本次指令未执行')
        issued = False
        try:
            if not self.link or action!='stop' and not self.state()['connected']:
                raise ValueError('P9主控未连接，本次未执行')
            if time.monotonic() > deadline:
                raise ValueError('请求过期，本次未执行')
            if action == 'stop':
                issued = True
                self.stop()
                return {'stopped': True}
            if action != 'run' and not self.control_verified:
                raise ValueError('四驱固件的软件检查或烧录回读未就绪，未执行')
            if action in ('start', 'run'):
                if action=='start' and not self.state()['capabilities']['drive_control']:
                    raise ValueError(self.state()['capabilities']['drive_reason'] or '驱动未就绪，未执行')
                if action=='run' and body.get('bench_confirmed') is not True:
                    raise ValueError('单轮诊断请先确认四轮悬空')
                if action=='start' and (body.get('mode')!='manual' or 'MANUAL_' not in self.identity):
                    raise ValueError('请刷新页面，使用手动拍摄固件开启')
                if self.latest['drive']['active'] or self.latest['motor_active'] or self.owner:
                    raise ValueError('已有控制或单轮测试，请先停止')
                if time.monotonic() > deadline:
                    raise ValueError('开启请求过期，本次未执行')
                if action == 'run':
                    channel = integer(body, 'channel', 1, 4)
                    issued = True
                    answer = self.exchange('BENCH_RUN_M'+str(channel), 'BENCH_RUN_STARTED,')
                    if answer != 'BENCH_RUN_STARTED,M'+str(channel):
                        raise ValueError('单轮起转回执不符')
                    return {'started': True, 'channel': channel, 'duration_ms': 2200}
                issued = True
                reply = self.exchange('DRIVE_ARM', 'DRIVE_ARMED,')
                self.generation = int(reply.split(',')[1])
                self.owner = secrets.token_urlsafe(18)
                self.seq = 0
                self.touched = time.monotonic()
                state = self.numbers('DRIVE_STATUS','DRIVE,',9)
                if state[1] != 1 or state[2] != 0 or state[3] != self.generation:
                    raise ValueError('主控未确认本次开启')
                self.latest = {**self.latest, 'drive':dict(active=True,moving=False,left_pwm=0,right_pwm=0,generation=self.generation,last_seq=0,reason=0)}
                return {'session': self.owner}
            if action not in ('set', 'brake') or not self.owner or body.get('session') != self.owner:
                raise ValueError('控制会话无效，请重新开启')
            seq = integer(body, 'seq', 1, 2147483647)
            if seq <= self.seq:
                raise ValueError('旧指令已拒绝')
            if time.monotonic()-self.touched >= .9:
                issued = True
                self.stop()
                raise ValueError('控制会话已过期')
            if action == 'brake':
                issued = True
                self.exchange(f'DRIVE_BRAKE,{self.generation},{seq}', 'DRIVE_BRAKED')
                left = right = 0
            else:
                throttle = integer(body, 'throttle', -100, 100)
                turn = integer(body, 'turn', -100, 100)
                limit = integer(body, 'limit', 1, 100)
                strafe=integer(body,'strafe',-100,100) if 'strafe' in body else 0
                if strafe and not self.is_mecanum():raise ValueError('当前固件不支持横移')
                left, right = throttle+turn, throttle-turn
                scale = max(100, abs(left), abs(right))
                left, right = round(left/scale*250*limit/100), round(right/scale*250*limit/100)
                issued = True
                if self.is_mecanum():
                    norm=max(100,abs(throttle)+abs(strafe)+abs(turn))
                    forward,lateral,yaw=[int(v/norm*250*limit/100) for v in (throttle,strafe,turn)]
                    self.exchange(f'DRIVE_VECTOR,{self.generation},{seq},{forward},{lateral},{yaw}','DRIVE_VECTOR_ACCEPTED')
                    left,right=forward+lateral+yaw,forward-lateral-yaw
                else:self.exchange(f'DRIVE_SET,{self.generation},{seq},{left},{right}', 'DRIVE_SET_ACCEPTED')
            self.seq = seq
            self.touched = time.monotonic()
            return {'ok': True, 'braked': action=='brake', 'left_pwm': left, 'right_pwm': right}
        except Exception:
            if issued:
                self.owner = None
                try: self.stop()
                except Exception: pass
            raise
        finally:
            self.lock.release()

    def worker(self):
        while not self.quit.is_set():
            with self.lock:
                try:
                    if self.link is None:
                        ports = [p for p in list_ports.comports() if (p.vid,p.pid)==(0x1a86,0x8010)]
                        if len(ports) != 1:
                            raise OSError('未识别到开发板P9，请连接电脑→P9；手机可继续充电')
                        self.link = serial.Serial(ports[0].device,115200,timeout=.01,write_timeout=.15)
                        self.buffer.clear()
                        self.link.write(b'\n')
                        identity = self.exchange('DRIVE_ID', 'DRIVE_ID,')
                        if identity not in ('DRIVE_ID,R1_GIMBAL_TIM5_20261020,1','DRIVE_ID,R1_GIMBAL_TIM5_P9_TX_20261021,1','DRIVE_ID,R1_DRIVE_STARTUP_STABLE_V2_20261021,1','DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_V3_20261021,1','DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_V4_20261021,1','DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_V5_20261021,1','DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_V6_20261021,1','DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_V7_20261023,1','DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_V8_20261023,1','DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_MECANUM_V2_20261107,1','DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_MECANUM_V3_20261107,1'):
                            raise ValueError('固件与当前调速页不匹配：'+identity)
                        expected = 'DRIVE_CAPS,5,250,600' if 'MANUAL_MECANUM_' in identity else 'DRIVE_CAPS,4,250,600' if ('MANUAL_V7' in identity or 'MANUAL_V8' in identity) else 'DRIVE_CAPS,3,250,600' if ('MANUAL_V5' in identity or 'MANUAL_V6' in identity) else 'DRIVE_CAPS,2,250,600' if ('STABLE_V2' in identity or 'MANUAL_' in identity) else 'DRIVE_CAPS,1,250,600'
                        if self.exchange('DRIVE_CAPS','DRIVE_CAPS,') != expected:
                            raise ValueError('固件幅度或租约与当前页面不匹配')
                        self.identity = identity.split(',')[1]
                        if self.is_mecanum() and self.exchange('DRIVE_CHASSIS','DRIVE_CHASSIS,')!=MECANUM_LAYOUTS[self.identity]:
                            raise ValueError('麦轮布局协议不符')
                        try:
                            self.line_supported=self.exchange('LINE_ID','LINE_ID,')=='LINE_ID,YB_8LP_UART4_PC10_PC11_STATIC_V1'
                        except (TimeoutError,ValueError):
                            self.line_supported=False
                        try:
                            self.mpu_supported=self.exchange('MPU_ID','MPU_ID,')=='MPU_ID,MPU6050_PD6_PD7_ADDR69_V1'
                        except (TimeoutError,ValueError):
                            self.mpu_supported=False
                        self.imu_observer_supported=False
                        if self.mpu_supported:
                            try:self.imu_observer_supported=self.exchange('MPU_FEATURES_ID','MPU_FEATURES_ID,')=='MPU_FEATURES_ID,IMU_OBSERVER_V1_20HZ'
                            except (TimeoutError,ValueError):pass
                        self.control_verified = not self.identity.startswith('R1_DRIVE_STARTUP')
                        if not self.control_verified:
                            ready_path=ROOT/'output/onboard_dashboard/drive-startup-20261021/ready.json'
                            if ready_path.exists():
                                ready=json.loads(ready_path.read_text(encoding='utf8'))
                                self.control_verified=ready.get('identity')==self.identity and ready.get('suspended_four_wheels_verified') is True
                    if 'MANUAL_' in self.identity:
                        manual_stem='r1_mecanum_groundmap' if self.identity=='R1_DRIVE_STARTUP_MANUAL_MECANUM_V3_20261107' else 'r1_mecanum_integrated' if self.is_mecanum() else 'r1_official_tt_v8' if ('MANUAL_V8' in self.identity or self.is_mecanum()) else 'r1_official_tt_v7' if ('MANUAL_V7' in self.identity or ('MANUAL_V8' in self.identity or self.is_mecanum())) else 'r1_official_tt_v6' if 'MANUAL_V6' in self.identity else 'r1_official_tt_v5' if ('MANUAL_V5' in self.identity or 'MANUAL_V6' in self.identity or ('MANUAL_V7' in self.identity or ('MANUAL_V8' in self.identity or self.is_mecanum()))) else 'r1_drive_startup_manual_v4' if 'MANUAL_V4' in self.identity else 'r1_drive_startup_manual_v3'
                        proof=ROOT/'知行回路软件/build'/manual_stem/'flash-verification.json'
                        tests=ROOT/'知行回路软件/build'/manual_stem/'controller-host-verification.json'
                        self.control_verified=proof.exists() and tests.exists() and json.loads(proof.read_text(encoding='utf8')).get('readback')=='PASS' and json.loads(tests.read_text(encoding='utf8')).get('result')=='PASS'
                    if self.owner and time.monotonic()-self.touched >= .9:
                        self.stop()
                    self.snapshot()
                    self.integration.poll(self)
                except Exception as error:
                    if self.link:
                        self.last_link_failure=dict(at=time.time(),error=str(error),command=self.pending_command,
                            ports=[dict(device=p.device,vid=p.vid,pid=p.pid) for p in list_ports.comports()])
                        self.log('link_failure_detail',data=self.last_link_failure)
                    self.log('link_error', error=str(error))
                    self.owner = None
                    self.integration.disconnect(error)
                    self.line_supported=False
                    self.mpu_supported=False
                    self.imu_observer_supported=False
                    self.latest = dict(connected=False,error=str(error),sampled=time.monotonic())
                    if self.link:
                        try: self.link.write(b'\nDRIVE_STOP\nMOTOR_STOP\nGIMBAL_STOP\n')
                        except Exception: pass
                        self.link.close()
                        self.link = None
            self.quit.wait(.12 if self.link else 1)
        with self.lock:
            if self.link:
                try: self.stop()
                except Exception: pass
                try: self.exchange('GIMBAL_STOP','GIMBAL_STOPPED')
                except Exception: pass
                self.link.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8795)
    parser.add_argument('--base',help='Reuse the current local control URL after a deliberate restart')
    args = parser.parse_args()
    out = ROOT/'output/onboard_dashboard/pc-speed-20261021'
    out.mkdir(parents=True,exist_ok=True)
    if args.base and not re.fullmatch(r'/[A-Za-z0-9_-]{24,64}',args.base):
        parser.error('Invalid control base')
    base = args.base or '/'+secrets.token_urlsafe(18)
    bench = Bench(out)
    class Handler(BaseHTTPRequestHandler):
        def send(self, code, value, kind='application/json; charset=utf-8'):
            if not isinstance(value, bytes): value=json.dumps(value,ensure_ascii=False).encode('utf8')
            self.send_response(code)
            for k,v in [('Content-Type',kind),('Content-Length',str(len(value))),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')]:self.send_header(k,v)
            self.end_headers()
            self.wfile.write(value)
        def do_GET(self):
            path=urlsplit(self.path).path
            if path in ('/','/install'):
                doc='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>知行回路</title><style>body{font:18px sans-serif;max-width:32em;margin:30px auto;padding:0 18px;line-height:1.7}a{display:block;padding:16px;background:#096b76;color:white;border-radius:10px;text-align:center;text-decoration:none}</style><h1>知行回路 · 麦轮调试</h1><p>请使用“启动调试台”打印的完整网页地址，查看实时数据并手动控制。</p><p>安卓0.28.7安装包；升级保留原应用和记录。</p><a href="/update.apk" download="zhixing-dashboard-0.28.7.apk">下载安卓0.28.7</a>'
                self.send(200,doc.encode('utf8'),'text/html; charset=utf-8')
            elif path==base+'/api/status':self.send(200,bench.state())
            elif path in (base,base+'/',base+'/desktop',base+'/mobile'):
                doc=(HERE/'index.html').read_text(encoding='utf8').replace('<body','<body data-base="'+base+'"',1).replace('="assets/','="'+base+'/assets/')
                doc=doc.replace('视频和状态保存在小安卓；停止保存后可下载 MP4，编码与丢帧情况另行记录。','本电脑保存原始画面和状态，可回放；当前电脑端不提供 MP4 导出。')
                self.send(200,doc.encode('utf8'),'text/html; charset=utf-8')
            elif path in ('/update.apk',base+'/update.apk'):
                apk=ROOT/'output/onboard_dashboard/gimbal-live-fix-20261107/zhixing-dashboard.apk'
                proof=apk.parent/'installation-status.json'
                verified=apk.exists() and proof.exists() and json.loads(proof.read_text(encoding='utf8')).get('apk_sha256')==__import__('hashlib').sha256(apk.read_bytes()).hexdigest()
                if verified:self.send(200,apk.read_bytes(),'application/vnd.android.package-archive')
                else:self.send(404,{'error':'新版安装包尚未构建'})
            elif path==base+'/api/camera/frame':
                frame,seq=bench.integration.camera.latest_frame()
                if frame is None:self.send(503,bench.integration.camera.status());return
                self.send_response(200);self.send_header('Content-Type','image/jpeg');self.send_header('Cache-Control','no-store');self.send_header('X-Frame-Seq',str(seq));self.send_header('Content-Length',str(len(frame)));self.end_headers();self.wfile.write(frame)
            elif path.startswith(base+'/api/'):
                try:
                    result=bench.integration.get(path[len(base+'/api/'):],urlsplit(self.path).query)
                    if result:self.send(result[0],result[1],result[2] or 'application/json; charset=utf-8')
                    else:self.send(404,{'error':'没有这个接口'})
                except (ValueError,OSError) as error:self.send(400,{'error':str(error)})
            elif path==base+'/speed':
                doc=(HERE/'speed.html').read_text(encoding='utf8').replace('__BASE__',base)
                self.send(200,doc.encode('utf8'),'text/html; charset=utf-8')
            elif path.startswith(base+'/assets/'):
                target=(HERE/path[len(base+'/'):]).resolve()
                if not target.is_relative_to((HERE/'assets').resolve()) or not target.is_file():
                    self.send(404,{'error':'文件不存在'});return
                kind='text/javascript' if target.suffix=='.js' else mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
                self.send(200,target.read_bytes(),kind+'; charset=utf-8')
            else:self.send(404,{'error':'请使用完整调速链接'})
        def do_POST(self):
            path=urlsplit(self.path).path
            actions={base+'/api/drive/'+a:a for a in ('start','set','brake','stop')}
            actions[base+'/api/bench/run']='run'
            for area,names in [('gimbal',('start','set','center','heartbeat','stop')),('mpu',('compat',)),('camera',('start','stop')),('record',('start','stop')),('photo',('capture',))]:
                for name in names:actions[base+'/api/'+area+'/'+name]=area+'/'+name
            if path not in actions:self.send(404,{'error':'没有这个操作'});return
            content_type=self.headers.get('Content-Type','').split(';')[0].strip().lower()
            stop_beacon=actions[path] in ('stop','gimbal/stop','record/stop') and content_type=='text/plain'
            if self.headers.get('Origin')!='http://'+self.headers.get('Host','') or not (content_type=='application/json' or stop_beacon):
                self.send(403,{'error':'请从调速页操作'});return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=512:raise ValueError('请求格式错误')
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict):raise ValueError('请求格式错误')
                bench.log('http_action',action=actions[path],body={k:v for k,v in body.items() if k!='session'})
                action=actions[path]
                if '/' in action:
                    code,result=bench.integration.post(action,body,bench.state)
                else:code,result=200,bench.command(action,body)
                self.send(code,result)
            except Exception as error:
                bench.log('http_error',action=actions[path],error=str(error))
                self.send(409,{'error':str(error)})
        def log_message(self,*_):pass
    class Server(ThreadingHTTPServer):allow_reuse_address=False
    server=Server((args.bind,args.port),Handler)
    server.daemon_threads=True
    lan=[]
    for entry in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET):
        ip=entry[4][0]
        if not ip.startswith(('127.','169.254.')) and ip not in lan:lan.append(ip)
    runtime=dict(pid=__import__('os').getpid(),bind=args.bind,port=args.port,base=base,demo=False,
        url=f'http://127.0.0.1:{args.port}{base}/speed',dashboard_url=f'http://127.0.0.1:{args.port}{base}/desktop',
        lan_urls=[f'http://{ip}:{args.port}{base}/speed' for ip in lan] if args.bind=='0.0.0.0' else [],
        dashboard_lan_urls=[f'http://{ip}:{args.port}{base}/desktop' for ip in lan] if args.bind=='0.0.0.0' else [],
        log=str(out/'serial-http.jsonl'),started=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat())
    (out/'runtime.json').write_text(json.dumps(runtime,ensure_ascii=False,indent=2),encoding='utf8')
    thread=threading.Thread(target=bench.worker,daemon=True);thread.start()
    print(json.dumps(runtime,ensure_ascii=False),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        bench.quit.set();server.server_close();thread.join(timeout=3);bench.integration.close();bench.raw.close()

if __name__=='__main__':main()

