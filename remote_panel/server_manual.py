"""Local telemetry and leased manual gimbal control, never forwards arbitrary UART text."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs
from datetime import datetime,timezone
import argparse,json,os,secrets,sys,threading,time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
import serial
import read_only_telemetry as telemetry
from gimbal_controls import Controls
from camera_preview import CameraPreview,settings
from session_recorder import Recorder
from diagnostic_journal import DiagnosticJournal
READS=telemetry.READS+(('GIMBAL_STATUS','GIMBAL,',10),('ULTRA_STATUS','ULTRA,',12))
controls=Controls(HERE);lock=threading.Lock();stopping=threading.Event()
camera=CameraPreview(HERE)
diagnostics=DiagnosticJournal(HERE/'diagnostics')
camera.on_event=diagnostics.event
recorder=Recorder(HERE/'recordings');camera.on_frame=recorder.on_frame
camera.recording_status=lambda:recorder.status()['active']
latest={'connected':False,'error':'等待主控数据','received_monotonic':0};last_reply=0

def gimbal(values):
    names=('ms','ready','active','mode','yaw_us','pitch_us','starts','stops','yaw_hz','pitch_hz')
    return dict(zip(names,values))
def public_state():
    with lock:data=dict(latest)
    age=time.monotonic()-data.pop('received_monotonic',0)
    data['age_ms']=round(age*1000) if age<86400 else None
    data['control']=controls.public()
    data['camera']=camera.status()
    data['recording']=recorder.status()
    data['diagnostics']=diagnostics.status()
    link_age=time.monotonic()-last_reply
    data['link_age_ms']=round(link_age*1000) if link_age<86400 else None
    if not data.get('connected') or link_age>3:
        data.update(connected=False,error=data.get('error') or '主控数据已过期',gimbal=None,ultrasonic=None)
        for key in ('distance_mm','voltage_mv','uptime_s','warning_mm','wheel_speeds_mm_s','muted','driver_state','guard_state','motion_active','motor_fault','uart_errors','uart_drops'):data[key]=None
    return data

def worker(port):
    global latest,last_reply
    while not stopping.is_set():
        try:
            with serial.Serial(port,115200,timeout=.08,write_timeout=.5) as link:
                diagnostics.event('serial_connected',port=port,baud=115200)
                if link.in_waiting:diagnostics.raw('RX',link.read(link.in_waiting),phase='before_handshake')
                def exchange(command,prefix):
                    global last_reply
                    packet=(command+'\n').encode('ascii')
                    diagnostics.raw('TX_ATTEMPT',packet)
                    written=link.write(packet);diagnostics.raw('TX_ACCEPTED',packet[:written])
                    deadline=time.monotonic()+.65
                    while time.monotonic()<deadline and not stopping.is_set():
                        raw=link.readline()
                        if raw:diagnostics.raw('RX',raw)
                        line=raw.decode('ascii',errors='replace').strip()
                        if line.startswith(prefix):last_reply=time.monotonic();return line
                        if line in ('GIMBAL_BUSY','GIMBAL_NOT_RUNNING','GIMBAL_SET_REJECTED'):
                            raise RuntimeError('主控拒绝云台操作：'+line)
                    raise TimeoutError('主控未回复：'+command)
                def snapshot():
                    values=[int(v) for v in exchange('GIMBAL_STATUS','GIMBAL,').split(',')[1:]]
                    if len(values)!=10:raise ValueError('云台状态格式错误')
                    return gimbal(values)
                try:
                    exchange('PING','PONG');snapshot()
                    with controls.lock:
                        if not controls.owner:controls.state='STOPPED';controls.error=None
                    rows={};at=0
                    while not stopping.is_set():
                        if not diagnostics.status()['ok']:
                            link.write(b'GIMBAL_STOP\nSTOP\n')
                            camera.stop();recorder.stop('原始日志写入失败')
                            raise RuntimeError('原始日志写入失败，已请求停止控制')
                        current=controls.service(exchange,snapshot)
                        if current:
                            with lock:
                                if latest.get('connected'):latest['gimbal']=current
                        command,prefix,count=READS[at]
                        values=[int(v) for v in exchange(command,prefix).split(',')[1:]]
                        if len(values)!=count:raise ValueError('状态格式错误：'+command)
                        diagnostics.event('decoded_reply',command=command,values=values)
                        rows[command]=values;at=(at+1)%len(READS)
                        if at==0:
                            data=telemetry.decode(rows);u=rows['ULTRA_STATUS']
                            data.update(mode='MANUAL_GIMBAL_ONLY',gimbal=gimbal(rows['GIMBAL_STATUS']),
                                ultrasonic={'valid':bool(u[1]) and u[2]==1,'status':u[2],
                                'distance_mm':u[3] if u[1] and u[2]==1 else None,'age_ms':u[10]})
                            with lock:latest=data
                            temp=HERE/'telemetry.tmp';temp.write_text(json.dumps(public_state(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(temp,HERE/'telemetry.json')
                        stopping.wait(.04)
                finally:
                    if controls.public()['active']:
                        try:
                            diagnostics.raw('TX_ATTEMPT',b'GIMBAL_STOP\n',phase='worker_exit')
                            written=link.write(b'GIMBAL_STOP\n');diagnostics.raw('TX_ACCEPTED',b'GIMBAL_STOP\n'[:written],phase='worker_exit')
                        except Exception:pass
        except Exception as error:
            diagnostics.event('serial_error',error=str(error))
            controls.disconnect(error)
            with lock:latest={**latest,'connected':False,'error':str(error)}
            stopping.wait(1)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial',default='COM5');parser.add_argument('--bind',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8766);args=parser.parse_args()
    base='/'+secrets.token_urlsafe(18)
    class Handler(BaseHTTPRequestHandler):
        def send(self,code,value,kind='application/json; charset=utf-8'):
            content=value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False).encode('utf-8')
            self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(content)));self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers();self.wfile.write(content)
        def do_GET(self):
            path=urlsplit(self.path).path
            if path in (base,base+'/'):self.send(200,(HERE/'index.html').read_bytes(),'text/html; charset=utf-8')
            elif path==base+'/api/status':self.send(200,public_state())
            elif path==base+'/api/camera/status':self.send(200,camera.status())
            elif path==base+'/api/record/status':self.send(200,recorder.status())
            elif path==base+'/api/record/list':self.send(200,recorder.sessions())
            elif path.startswith(base+'/api/record/'):
                try:
                    pieces=path[len(base+'/api/record/'):].split('/')
                    if len(pieces)!=2:raise ValueError('记录地址无效')
                    sid,action=pieces
                    if action=='data':self.send(200,recorder.replay(sid))
                    elif action=='frame':
                        query=parse_qs(urlsplit(self.path).query)
                        if set(query)!={'index'} or len(query['index'])!=1:raise ValueError('帧编号无效')
                        self.send(200,recorder.frame(sid,int(query['index'][0])),'image/jpeg')
                    else:raise ValueError('记录地址无效')
                except (ValueError,OSError) as error:self.send(400,{'error':str(error)})
            elif path==base+'/api/camera/frame':
                frame,seq=camera.latest_frame()
                if frame is None:self.send(503,camera.status());return
                self.send_response(200);self.send_header('Content-Type','image/jpeg')
                self.send_header('Cache-Control','no-store');self.send_header('X-Frame-Seq',str(seq))
                self.send_header('Content-Length',str(len(frame)));self.end_headers();self.wfile.write(frame)
            else:self.send(404,{'error':'页面不存在'})
        def do_POST(self):
            path=urlsplit(self.path).path
            if not path.startswith(base+'/api/gimbal/') and path not in (base+'/api/camera/start',base+'/api/camera/stop',base+'/api/record/start',base+'/api/record/stop'):self.send(404,{'error':'没有这个操作'});return
            origin='http://'+self.headers.get('Host','')
            if self.headers.get('Origin')!=origin or self.headers.get('Content-Type','').split(';')[0]!='application/json':
                self.send(403,{'error':'请从当前控制页面操作'});return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=512:raise ValueError()
                body=json.loads(self.rfile.read(size))
            except (ValueError,TypeError):self.send(400,{'error':'请求格式错误'});return
            diagnostics.event('ui_request',action=path[len(base+'/api/'):],body={k:v for k,v in body.items() if k!='session'} if isinstance(body,dict) else body)
            if not diagnostics.status()['ok']:self.send(503,{'error':'原始日志无法保存，控制已暂停'});return
            if path in (base+'/api/record/start',base+'/api/record/stop'):
                if body!={}:self.send(400,{'error':'请求格式错误'});return
                try:
                    result=recorder.start(public_state) if path.endswith('/start') else recorder.stop()
                    diagnostics.event('record_action_result',action=path.rsplit('/',1)[-1],result=result);self.send(200,result)
                except (ValueError,OSError) as error:diagnostics.event('record_action_error',error=str(error));self.send(400,{'error':str(error)})
                return
            if path in (base+'/api/camera/start',base+'/api/camera/stop'):
                if path.endswith('/stop') and body!={}:self.send(400,{'error':'请求格式错误'});return
                try:
                    chosen=settings(body) if path.endswith('/start') else None
                except ValueError as error:self.send(400,{'error':str(error)});return
                if chosen and (recorder.status()['active'] or recorder.status()['finishing']):self.send(409,{'error':'请先停止记录，再切换画质'});return
                if not chosen:recorder.stop('画面关闭')
                try:
                    result=camera.start(*chosen) if chosen else camera.stop()
                    diagnostics.event('camera_action_result',action=path.rsplit('/',1)[-1],result=result);self.send(200,result)
                except Exception as error:diagnostics.event('camera_action_error',error=str(error));self.send(503,{'error':str(error)})
                return
            action=path[len(base+'/api/gimbal/'):]
            code,value=controls.submit(action,body)
            diagnostics.event('ui_response',action=action,code=code,result={k:v for k,v in value.items() if k!='session'})
            self.send(code,value)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer((args.bind,args.port),Handler)
    runtime={'pid':os.getpid(),'serial':args.serial,'bind':args.bind,'port':args.port,
             'url':f'http://{args.bind}:{args.port}{base}/','mode':'PC_MANUAL_GIMBAL',
             'started_at':datetime.now(timezone.utc).isoformat(),'vehicle_motion':'DISABLED'}
    (HERE/'runtime.json').write_text(json.dumps(runtime,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    thread=threading.Thread(target=worker,args=(args.serial,),daemon=True);thread.start()
    print(json.dumps(runtime,ensure_ascii=False),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:stopping.set();recorder.stop('服务关闭');camera.stop();server.server_close();thread.join(timeout=2);diagnostics.close()
if __name__=='__main__':main()
