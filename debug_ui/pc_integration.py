"""Comprehensive console adapters sharing the speed service's single P9 owner."""
from pathlib import Path
from urllib.parse import parse_qs
import datetime, json, re, sys, time, queue, threading

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'remote_panel'))
from gimbal_controls import Controls
from camera_preview import CameraPreview, settings
from session_recorder import Recorder
from read_only_telemetry import READS, decode
from line_telemetry import decode_line
from mpu_telemetry import decode_mpu,age_mpu,decode_features
import zlib

GROUND_REASON='驱动控制线断开后曾继续转动；独立电机断电或驱动端失联停机尚未验收，当前只开放架空控制。'

class Integration:
    def __init__(self,folder):
        self.folder=folder
        self.controls=Controls(folder)
        self.camera=CameraPreview(folder)
        self.recorder=Recorder(folder/'recordings')
        self.camera.on_frame=self.recorder.on_frame
        self.camera.recording_status=lambda:self.recorder.status()['active']
        self.rows={};self.at=0;self.telemetry={};self.gimbal=None;self.ultra=None;self.sampled=0
        self.gimbal_diagnostics=None;self.diagnostics_at=0
        self.p7_usb=None;self.usb_at=0
        self.line=None;self.line_at=0
        self.sensor_requests=queue.Queue(maxsize=2)
        self.mpu=None;self.mpu_at=0;self.mpu_failures=0
        calibration=HERE.parents[1]/'output/onboard_dashboard/mpu6050-20261025'
        try:
            self.mpu_reference=json.loads((calibration/'flat-reference.json').read_text(encoding='utf-8'))
            self.mpu_mapping=json.loads((calibration/'body-axis-mapping.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):self.mpu_reference=self.mpu_mapping=None
        try:self.mpu_crc=zlib.crc32((calibration/'flat-reference.json').read_bytes()+(calibration/'body-axis-mapping.json').read_bytes())&0xffffffff
        except OSError:self.mpu_crc=None
        self.photos=folder/'photos';self.photos.mkdir(exist_ok=True)

    def gimbal_snapshot(self,bench):
        values=bench.numbers('GIMBAL_STATUS','GIMBAL,',10)
        self.gimbal=dict(zip(('ms','ready','active','mode','yaw_us','pitch_us','starts','stops','yaw_hz','pitch_hz'),values))
        return self.gimbal

    def disconnect(self,error):
        while True:
            try:
                request=self.sensor_requests.get_nowait();request['response']=(503,{'error':'主控连接已断开，兼容采集未执行'});request['done'].set()
            except queue.Empty:break
        self.controls.disconnect(error)
        # A new serial connection starts a new sensor cycle; never mix sessions.
        self.rows={};self.at=0;self.telemetry={};self.gimbal=None;self.ultra=None;self.sampled=0
        self.gimbal_diagnostics=None;self.diagnostics_at=0
        self.p7_usb=None;self.usb_at=0
        self.line=None;self.line_at=0
        self.mpu=None;self.mpu_at=0;self.mpu_failures=0

    def poll(self,bench):
        self.controls.service(bench.exchange,lambda:self.gimbal_snapshot(bench))
        self.service_sensor_requests(bench)
        if getattr(bench,'line_supported',False) and time.monotonic()-self.line_at>.35:
            analog=bench.numbers('LINE_ANALOG','LINE_ANALOG,',10)
            digital=bench.numbers('LINE_DIGITAL','LINE_DIGITAL,',3)
            status=bench.numbers('LINE_STATUS','LINE_STATUS,',12)
            self.line=decode_line(analog,digital,status);self.line_at=time.monotonic()
            bench.log('line_readonly_snapshot',data=self.line)
        if getattr(bench,'mpu_supported',False) and self.mpu_failures<3 and time.monotonic()-self.mpu_at>.35:
            try:
                raw=bench.numbers('MPU_RAW','MPU_RAW,',9)
                status=bench.numbers('MPU_STATUS','MPU_STATUS,',11)
                self.mpu=decode_mpu(raw,status,self.mpu_reference,self.mpu_mapping)
                if getattr(bench,'imu_observer_supported',False):
                    self.mpu=decode_features(bench.numbers('MPU_FEATURES','MPU_FEATURES,',17),self.mpu,self.mpu_crc)
                self.mpu_failures=0;bench.log('mpu_readonly_snapshot',data=self.mpu)
            except (TimeoutError,ValueError) as error:
                self.mpu_failures+=1;self.mpu=None;bench.log('mpu_readonly_error',error=str(error))
            self.mpu_at=time.monotonic()
        if 'MANUAL_' in bench.identity and time.monotonic()-self.usb_at>2:
            usb=bench.numbers('USB_STATUS','USB_STATUS,',13)
            self.p7_usb=dict(zip(('ms','address','configured','enumerated','sleeping','reset_count','rx_bytes','tx_queued','rejected','overflows','tx_remaining','endpoint_busy','interrupt_flags'),usb))
            self.p7_usb['sampled_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.usb_at=time.monotonic();bench.log('p7_readonly_diagnostics',data=self.p7_usb)
        if not self.controls.public()['active'] and time.monotonic()-self.diagnostics_at>10:
            pins=bench.exchange('GIMBAL_PINS','GIMBAL_PINS,')
            hw=bench.numbers('GIMBAL_HW','GIMBAL_HW,',7)
            lease=bench.numbers('GIMBAL_RANDOM_STATUS','RANDOM,',5)
            self.gimbal_diagnostics=dict(pins=pins,prescaler=hw[0],period=hw[1],yaw_compare=hw[2],pitch_compare=hw[3],ccer=hw[4],timer_control=hw[5],gpio_config=hw[6],lease_age_ms=lease[3],lease_stop_count=lease[4],sampled_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
            self.diagnostics_at=time.monotonic()
            bench.log('gimbal_readonly_diagnostics',data=self.gimbal_diagnostics)
        reads=READS+(('GIMBAL_STATUS','GIMBAL,',10),('ULTRA_STATUS','ULTRA,',12))
        command,prefix,count=reads[self.at]
        self.rows[command]=bench.numbers(command,prefix,count)
        if command=='GIMBAL_STATUS':
            self.gimbal=dict(zip(('ms','ready','active','mode','yaw_us','pitch_us','starts','stops','yaw_hz','pitch_hz'),self.rows[command]))
            self.controls.observe_link(self.gimbal)
        self.at=(self.at+1)%len(reads)
        if self.at==0:
            self.telemetry=decode(self.rows);self.sampled=time.monotonic()
            # A current control snapshot may be newer than this sensor group.
            u=self.rows['ULTRA_STATUS']
            self.ultra=dict(valid=bool(u[1]) and u[2]==1,status=u[2],distance_mm=u[3] if u[1] and u[2]==1 else None,age_ms=u[10])

    def enrich(self,data):
        # Slow sensor groups retain their own age; fresh motor packets do not renew them.
        sensor_age=(time.monotonic()-self.sampled)*1000
        data={**self.telemetry,**data}
        data['link_age_ms']=data['age_ms']
        data['age_ms']=max(data['age_ms'] or 0,round(sensor_age)) if self.sampled else None
        if not data['connected'] or not self.sampled or sensor_age>3000:
            data.update(range_valid=False,distance_mm=None,voltage_mv=None,wheel_speeds_mm_s=None,gimbal=None,ultrasonic=None)
        else:
            data.update(gimbal=self.gimbal,ultrasonic=self.ultra,wheel_speeds_mm_s=data.get('wheel_speeds'))
        data.update(control=self.controls.public(),camera=self.camera.status(),recording=self.recorder.status(),
                    gimbal_diagnostics=self.gimbal_diagnostics,p7_usb=self.p7_usb,
                    mode='PC_COMPREHENSIVE',diagnostics=dict(ok=True,active=True,id=self.folder.name))
        data['line_task']=dict(supported=False,available=False,active=False,message='自动巡线请使用车载小手机App，并将手机接回P7；电脑P9页面提供手动遥控。')
        line_age=(time.monotonic()-self.line_at)*1000 if self.line_at else 1e9
        data['line']=None
        data['mpu']=age_mpu(self.mpu,(time.monotonic()-self.mpu_at)*1000,data['connected'])
        if self.line and data['connected']:
            data['line']={**self.line,'age_ms':round(self.line['age_ms']+line_age),
                          'valid':self.line['valid'] and line_age<1500}
        data['capabilities'].update(gimbal_control=data['connected'] and self.gimbal is not None,mpu_compatibility=True,
                                    ground_control=data['capabilities']['drive_control'] and 'MANUAL_' in data.get('firmware',''),range_interlock=False if 'MANUAL_' in data.get('firmware','') else True,ground_driving_verified=False,motor_pwm_limit=None if ('MANUAL_V5' in data.get('firmware','') or 'MANUAL_V6' in data.get('firmware','') or 'MANUAL_V7' in data.get('firmware','') or ('MANUAL_V8' in data.get('firmware','') or 'MANUAL_MECANUM_' in data.get('firmware',''))) else 900 if 'MANUAL_V4' in data.get('firmware','') else 375,driver_pwm_range=3600,driver_speed_limit=data.get('driver_speed_limit',120),ground_reason=data['capabilities'].get('drive_reason') or '四轮手动遥控；测距只提示。麦轮当前仅完成悬空验证，落地表现待验；驱动线断开后独立停车仍待验证。')
        return data

    def get(self,route,query):
        if route=='ui/info':return 200,dict(demo=False,platform='PC',storage='电脑',realtime={},version='2026.11.06',wheel_type='ordinary',mpu_compatibility=True),None
        if route=='camera/status':return 200,self.camera.status(),None
        if route=='record/status':return 200,self.recorder.status(),None
        if route=='record/list':return 200,[dict(s,video_ready=False) for s in self.recorder.sessions()],None
        if route=='photo/list':return 200,[dict(id=p.stem) for p in sorted(self.photos.glob('*.jpg'),reverse=True)],None
        if re.fullmatch(r'photo/[0-9T-]+/download',route):return 200,(self.photos/(route.split('/')[1]+'.jpg')).read_bytes(),'image/jpeg'
        match=re.fullmatch(r'record/([^/]+)/(data|frame)',route)
        if match:
            sid,action=match.groups()
            if action=='data':return 200,self.recorder.replay(sid),None
            args=parse_qs(query)
            if set(args)!={'index'} or len(args['index'])!=1:raise ValueError('帧编号无效')
            return 200,self.recorder.frame(sid,int(args['index'][0])),'image/jpeg'
        return None

    def post(self,route,body,state):
        if route=='mpu/compat':
            if set(body)!={'enable','identity'} or body['enable'] is not True or type(body['identity']) is not int or body['identity']!=0x72:raise ValueError('请明确选择本次0x72兼容采集')
            request=dict(deadline=time.monotonic()+2,done=threading.Event(),response=None,cancelled=False)
            try:self.sensor_requests.put_nowait(request)
            except queue.Full:return 409,{'error':'兼容采集请求正在处理'}
            if not request['done'].wait(2.4):request['cancelled']=True;return 503,{'error':'兼容采集尚未确认，请查看传感器状态'}
            return request['response']
        if route.startswith('gimbal/'):return self.controls.submit(route[7:],body)
        if route=='camera/start':
            if self.recorder.status()['active']:raise ValueError('请先停止记录')
            return 200,self.camera.start(*settings(body))
        if route=='camera/stop':self.recorder.stop('画面关闭');return 200,self.camera.stop()
        if route=='record/start':
            if not self.camera.status().get('valid'):raise ValueError('没有新鲜真实画面，未开始记录')
            return 200,self.recorder.start(state)
        if route=='record/stop':return 200,self.recorder.stop()
        if route=='photo/capture':
            if not self.camera.status().get('valid'):raise ValueError('没有新鲜真实画面，未拍照')
            frame,_=self.camera.latest_frame()
            if frame is None:raise ValueError('没有新鲜真实画面')
            photo_id=datetime.datetime.now().strftime('%Y%m%dT%H%M%S-%f')
            (self.photos/(photo_id+'.jpg')).write_bytes(frame)
            return 200,dict(id=photo_id)
        raise ValueError('没有这个操作')

    def service_sensor_requests(self,bench):
        try:request=self.sensor_requests.get_nowait()
        except queue.Empty:return
        try:
            if request['cancelled'] or time.monotonic()>request['deadline']:raise ValueError('兼容采集请求已过期，未执行')
            if bench.owner or bench.latest.get('drive',{}).get('active') or self.controls.public()['active'] or self.gimbal and self.gimbal.get('active'):raise ValueError('请先停止车轮和云台，再启用兼容采集')
            status=bench.numbers('MPU_STATUS','MPU_STATUS,',11)
            if status[4]!=0x72 or status[1]:raise ValueError('当前传感器不是等待兼容的0x72设备')
            reply=bench.exchange('MPU_COMPAT_ON','MPU_COMPAT_ON,')
            if reply!='MPU_COMPAT_ON,TRIAL_ID72':raise ValueError('主控未接受本次兼容采集')
            self.mpu_failures=0;self.mpu_at=0
            request['response']=(200,dict(ok=True,message='本次兼容采集已接受，等待有效姿态；重启后需重新选择'))
        except (ValueError,OSError,TimeoutError) as error:request['response']=(409,{'error':str(error)})
        finally:request['done'].set()

    def close(self):
        self.recorder.stop('服务关闭');self.camera.stop()
