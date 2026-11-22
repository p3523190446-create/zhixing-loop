"""Explicit UI-only test fixture. No serial, camera, ADB, files from real runs or hardware writes."""
from pathlib import Path
from urllib.parse import parse_qs
import json, math, threading, time

JSON = 'application/json; charset=utf-8'
SID = '20261013-000000-de0001'

class DemoBackend:
    def __init__(self):
        self.lock = threading.RLock()
        self.start = time.monotonic()
        self.active = False
        self.drive_active = False
        self.drive_seq = 0
        self.drive_left = self.drive_right = 0
        self.drive_touch = 0
        self.photos = []
        self.camera_on = False
        self.record_on = False
        self.last_touch = 0
        self.yaw = self.pitch = 0
        self.resolution = '640x480'
        self.fps = 15
        self.seq = 0
        self.events = []
        self.offline = False
        self.reject_start = False
        self.record_started = 0
        self.record_frames = 0
        self.record_id = None
        self.segment = 0
        self.event_file = Path(__file__).parent / 'demo-events.jsonl'
        self.event_file.write_text('', encoding='utf-8')
    def camera(self):
        w,h = map(int,self.resolution.split('x'))
        return {'running':self.camera_on,'valid':self.camera_on,'width':w,'height':h,'requested_fps':self.fps,'recording':self.record_on,'seq':self.seq,'age_ms':40,'error':None}
    def record(self):
        duration = time.monotonic()-self.record_started if self.record_on else 6.0 if self.record_id else 0
        return {'active':self.record_on,'finishing':False,'id':self.record_id,'duration_s':round(duration,1),'frames':int(duration*self.fps),'samples':int(duration),'bytes':int(duration*30000),'dropped_frames':0,'reason':'演示记录，不落盘视频','error':None,'video_ready':not self.record_on and self.record_id is not None,'video_format':'video/mp4'}
    def status(self):
        if self.active and time.monotonic()-self.last_touch>1.8:self.active=False
        if self.drive_active and time.monotonic()-self.drive_touch>.6:self.drive_active=False;self.drive_left=self.drive_right=0
        t=time.monotonic()-self.start
        return {'connected':not self.offline,'link_age_ms':0 if not self.offline else 6000,'age_ms':100,'received_at':round(t,1),'uptime_s':int(t),'range_valid':True,'distance_mm':int(320+80*math.sin(t/4)),'voltage_mv':7420,'warning_mm':120,'muted':False,'guard_state':0,'driver_state':1,'motor_fault':0,'wheel_speeds_mm_s':[0,0,0,0],'uart_errors':0,'uart_drops':0,'motion_active':False,'error':'演示断线' if self.offline else None,'gimbal':{'ready':not self.offline,'active':self.active,'yaw_us':1500+5*self.yaw if self.active else 0,'pitch_us':1500+5*self.pitch if self.active else 0},'ultrasonic':{'valid':True,'distance_mm':int(340+80*math.sin(t/4)),'age_ms':80},'drive':{'active':self.drive_active,'left_pwm':self.drive_left,'right_pwm':self.drive_right,'mode':'BENCH_ONLY'},'capabilities':{'drive_control':not self.offline,'gimbal_control':not self.offline},'control':{'active':self.active,'target':{'yaw':self.yaw,'pitch':self.pitch},'events':self.events[-4:]},'diagnostics':{'id':'DEMO-UI-ONLY','ok':True,'seq':len(self.events),'segments':1},'camera':self.camera(),'recording':self.record()}
    def image(self):
        self.seq += 1
        w,h=map(int,self.resolution.split('x'))
        svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 640 480"><rect width="640" height="480" fill="#102229"/><path d="M0 360L220 160H420L640 360V480H0Z" fill="#1b383b"/><g stroke="#365354" stroke-width="2"><path d="M0 380H640M0 430H640M0 480H640M320 160V480M220 160L70 480M420 160L570 480"/></g><rect x="40" y="130" width="100" height="200" rx="3" fill="#34504c"/><path d="M55 170H125M55 215H125M55 260H125" stroke="#79968a" stroke-width="7"/><rect x="490" y="160" width="100" height="170" fill="#355049"/><rect x="276" y="210" width="100" height="110" rx="4" fill="#809283"/><rect x="258" y="190" width="135" height="155" rx="6" fill="none" stroke="#a9e4c3" stroke-width="2"/><text x="260" y="179" fill="#a9e4c3" font-family="sans-serif" font-size="13">DEMO TARGET</text><path d="M310 240H330M320 230V250" stroke="#d3e7dd"/><text x="20" y="450" fill="#b9cfc9" font-family="sans-serif" font-size="14">SIMULATED FRAME {self.seq} / UI ONLY</text></svg>'''
        # This synthetic illustration fills its declared demo resolution.
        # Real camera images are never resized or cropped by this fixture.
        svg=svg.replace('viewBox="0 0 640 480"','viewBox="0 0 640 480" preserveAspectRatio="xMidYMid slice"')
        return svg.encode('utf-8')
    def request(self, method, path, query, body):
        with self.lock:
            if method=='POST':
                # Session credentials are excluded from this UI-only test log.
                row={'path':path,'body':{k:v for k,v in body.items() if k!='session'},'t':time.monotonic()-self.start}
                with self.event_file.open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
            if method=='GET':
                if path=='status':return 200,self.status(),JSON,None
                if path=='camera/status':return 200,self.camera(),JSON,None
                if path=='record/status':return 200,self.record(),JSON,None
                if path=='camera/frame':return (200,self.image(),'image/svg+xml',self.seq) if self.camera_on else (503,{'error':'演示画面未开启'},JSON,None)
                if path=='photo/list':return 200,self.photos,JSON,None
                if path.startswith('photo/') and path.endswith('/download'):return 200,self.image(),'image/svg+xml',self.seq
                if path=='record/'+SID+'/download':return 200,b'SIMULATED DOWNLOAD ROUTE TEST ONLY; NOT A REAL VIDEO','application/octet-stream',None
                if path=='record/list':return 200,[{'video_ready':self.record_id is not None and not self.record_on,'id':SID,'started_at':'2026-10-13T00:00:00+08:00','duration_s':6,'state':'COMPLETE','frames':60}],JSON,None
                if path=='record/'+SID+'/data':return 200,{'meta':{'duration_s':6,'state':'COMPLETE'},'frames':[{'t':i/10} for i in range(60)],'samples':[{'t':i,'state':self.status()} for i in range(6)]},JSON,None
                if path=='record/'+SID+'/frame':return 200,self.image(),'image/svg+xml',self.seq
                return 404,{'error':'没有这条演示记录'},JSON,None
            if path=='demo/scenario':
                self.offline=bool(body.get('offline',False));self.reject_start=bool(body.get('reject_start',False))
                if self.offline:self.active=False;self.drive_active=False;self.drive_left=self.drive_right=0
                return 200,{'ok':True},JSON,None
            if path.startswith('drive/'):
                action=path.split('/')[1]
                if action=='stop':self.drive_active=False;self.drive_left=self.drive_right=0;return 200,{'ok':True,'stopped':True},JSON,None
                if self.offline:return 503,{'error':'模拟断线'},JSON,None
                if action=='start':
                    if self.drive_active or body.get('bench_confirmed') is not True:return 409,{'error':'模拟台架条件未满足'},JSON,None
                    self.drive_active=True;self.drive_seq=0;self.drive_touch=time.monotonic();return 200,{'ok':True,'session':'demo-drive-lease'},JSON,None
                if not self.drive_active or body.get('session')!='demo-drive-lease':return 409,{'error':'模拟四驱会话已撤销'},JSON,None
                if type(body.get('seq')) is not int or body['seq']<=self.drive_seq:return 409,{'error':'旧序号'},JSON,None
                self.drive_seq=body['seq'];self.drive_touch=time.monotonic()
                if action=='brake':self.drive_left=self.drive_right=0;return 200,{'ok':True,'braked':True},JSON,None
                if action=='set':
                    if not all(type(body.get(k)) is int and -100<=body[k]<=100 for k in ('throttle','turn')):return 400,{'error':'输入越界'},JSON,None
                    if type(body.get('limit')) is not int or not 1<=body['limit']<=100:return 400,{'error':'上限越界'},JSON,None
                    l=body['throttle']+body['turn'];r=body['throttle']-body['turn'];scale=max(100,abs(l),abs(r))
                    self.drive_left=round(l/scale*250*body['limit']/100);self.drive_right=round(r/scale*250*body['limit']/100)
                    return 200,{'ok':True,'left_pwm':self.drive_left,'right_pwm':self.drive_right},JSON,None
                return 400,{'error':'未知四驱操作'},JSON,None
            if path=='photo/capture':
                if not self.camera_on:return 503,{'error':'模拟画面未开启'},JSON,None
                photo={'id':'20261020-000000-'+format(len(self.photos)+1,'06x'),'frame_seq':self.seq,'source':'SIMULATED_UI_ONLY'};self.photos.insert(0,photo)
                return 200,photo,JSON,None
            if path.startswith('gimbal/'):
                action=path.split('/')[1]
                if action=='stop':self.active=False;return 200,{'ok':True,'stopped':True},JSON,None
                if self.offline or self.reject_start and action=='start':return 503,{'error':'模拟主控拒绝/断线'},JSON,None
                if action=='start':self.active=True;self.yaw=self.pitch=0;self.last_touch=time.monotonic();return 200,{'ok':True,'session':'demo-lease'},JSON,None
                if not self.active or body.get('session')!='demo-lease':return 409,{'error':'模拟会话已失效'},JSON,None
                if action=='set':
                    if not all(type(body.get(k)) is int and -100<=body[k]<=100 for k in ('yaw','pitch')):return 400,{'error':'模拟指令越界'},JSON,None
                    self.yaw,self.pitch=body['yaw'],body['pitch']
                if action=='center':self.yaw=self.pitch=0
                self.last_touch=time.monotonic();self.events.append({'message':'模拟主控回执 · '+action})
                return 200,{'ok':True},JSON,None
            if path=='camera/start':self.camera_on=True;self.resolution=body['resolution'];self.fps=body['fps'];return 200,self.camera(),JSON,None
            if path=='camera/stop':self.camera_on=False;self.record_on=False;return 200,self.camera(),JSON,None
            if path=='record/start':
                if not self.camera_on:return 400,{'error':'模拟相机未就绪'},JSON,None
                self.record_on=True;self.segment+=1;self.record_id=SID;self.record_started=time.monotonic();return 200,self.record(),JSON,None
            if path=='record/stop':self.record_on=False;return 200,self.record(),JSON,None
            return 404,{'error':'没有这个演示接口'},JSON,None
