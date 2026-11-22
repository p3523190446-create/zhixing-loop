"""Local algorithms and desktop target tracking, consuming the existing P9 service.

Only local tracking-computation settings can be posted; no actuator API is exposed.
"""
import bootstrap
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse, datetime, json, math, os, threading, time, urllib.request
import cv2 as cv
import numpy as np
from collections import deque
from core import LineFollower, Vision
from tracking import TargetTracker
from events import EventStore

HERE = Path(__file__).resolve().parent
ROOT = bootstrap.ROOT
RUNTIME = ROOT/'output/onboard_dashboard/pc-speed-20261021/runtime.json'
OUT = ROOT/'output/onboard_dashboard/algorithms-20261025'

def timestamp():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()

def finite_age(value,limit):
    return type(value) in (int,float) and math.isfinite(value) and 0<=value<limit

class Source:
    def __init__(self,local_camera=None):
        self.local_camera=local_camera
        self.refresh()

    def refresh(self):
        runtime = json.loads(RUNTIME.read_text(encoding='utf-8'))
        # Do not use a network address from a runtime file; pin to the local service.
        base = runtime['base']
        import re
        if not re.fullmatch('/[A-Za-z0-9_-]{24,64}', base):
            raise ValueError('Invalid current dashboard path')
        self.url = 'http://127.0.0.1:8795' + base

    def get(self, endpoint, binary=False):
        if endpoint not in ('status','camera/status','camera/frame'):
            raise ValueError('Read endpoint not allowed')
        if self.local_camera and endpoint=='camera/status':return self.local_camera.status()
        if self.local_camera and endpoint=='camera/frame':
            frame,seq=self.local_camera.latest_frame()
            if frame is None:raise OSError('所选相机还没有新鲜画面')
            return frame,seq
        with urllib.request.urlopen(self.url+'/api/'+endpoint, timeout=3) as response:
            data = response.read(4*1024*1024+1)
            if len(data)>4*1024*1024: raise ValueError('Oversize source response')
            if binary: return data,response.headers.get('X-Frame-Seq')
            return json.loads(data)

class Lab:
    def __init__(self, record_seconds=60,borrowed_camera=False,original_camera=False):
        if borrowed_camera and original_camera:raise ValueError('Select only one camera')
        self.local_camera=None
        if borrowed_camera or original_camera:
            from borrowed_camera import BorrowedCamera
            self.local_camera=BorrowedCamera(OUT,kind='original' if original_camera else 'borrowed')
            self.local_camera.start()
        self.source = Source(self.local_camera)
        self.line = LineFollower()
        self.vision = Vision(HERE/'vendor/opencv_zoo_yolox')
        self.tracker=TargetTracker()
        self.lock = threading.Lock()
        self.quit = threading.Event()
        self.data = dict(connected=False,vision_valid=False,error='正在连接',actuation_enabled=False)
        self.image = None
        self.image_at = 0
        self.image_seq=None
        self.image_source_at=None
        self.detection_times=deque(maxlen=20)
        self.session = OUT/('run-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
        self.session.mkdir(parents=True,exist_ok=False)
        self.events=EventStore(self.session)
        self.started = time.monotonic()
        self.record_until = self.started+record_seconds
        self.recorded = 0
        self.record_bytes = 0
        self.last_recorded = 0
        self.journal = (self.session/'samples.jsonl').open('w',encoding='utf-8')
        (self.session/'session.json').write_text(json.dumps(dict(
            started=timestamp(),mode='live_shadow',actuation_enabled=False,
            recording_seconds=record_seconds,training_ready=False,
            synchronization='Host receive times and source ages; no hardware exposure timestamp. '
                'A frame and status are associated observations, not exact synchronized ground truth.',
            camera_pose='desktop_camera_mount_unverified',camera_source=self.local_camera.source if self.local_camera else 'P9 service camera',model='OpenCV Zoo YOLOX-s',
            backend=self.vision.backend),indent=2),encoding='utf-8')

    def state(self):
        with self.lock:
            d = dict(self.data)
            if self.local_camera:d['camera_source']=self.local_camera.status()
            elapsed=max(0,time.monotonic()-d.get('line_received_monotonic',d.get('updated_monotonic',time.monotonic())))
            if d.get('line'):
                line=dict(d['line'])
                if type(line.get('age_ms')) in (int,float):line['age_ms']+=round(elapsed*1000)
                if not finite_age(line.get('age_ms'),500):
                    line.update(valid=False,state='offline',position=None,correction=None,dark=[],strengths=[])
                d['line']=line
            if self.image_at:
                d['result_age_ms'] = round((time.monotonic()-self.image_at)*1000)
                if d['result_age_ms']+d.get('source_age_ms',0)>=250 and d.get('tracking'):
                    d['tracking']={**d['tracking'],'state':'STALE','pointing_request':None,'bbox':None}
                if d['result_age_ms'] + d.get('source_age_ms',0) >= 1500:
                    d.update(vision_valid=False,vision=None)
            if time.monotonic()-d.get('updated_monotonic',0)>2:
                d.update(connected=False,line=None,vision_valid=False,vision=None,
                         error='计算或上游连接中断，结果已失效')
            if not d.get('vision_valid') and d.get('tracking'):
                d['tracking']={**d['tracking'],'state':'STALE','pointing_request':None,'bbox':None}
            return d

    def worker(self):
        last_key = None
        last_tag = None
        tag_streak = 0
        while not self.quit.is_set():
            if self.local_camera and last_key:
                fresh=self.local_camera.status()
                if fresh['valid'] and str(fresh['seq'])==last_key[0]:
                    self.quit.wait(.003);continue
            start = time.monotonic()
            row = dict(at=timestamp(),updated_monotonic=start,actuation_enabled=False,
                       source='PC_CAMERA_'+self.local_camera.kind.upper() if self.local_camera else 'PC_P9_AND_EXTERNAL_USB',vision_valid=False,vision=None,
                       recording_samples=self.recorded,recording_active=start<self.record_until,
                       odometry=dict(valid=False,reason='轮速单位、实测轮距和转向参数尚未标定'),
                       training_ready=False,model_ready=self.vision.model is not None,
                       model_backend=self.vision.backend,
                       model_load_error=self.vision.model_error)
            frame = None
            record_frame = None
            try:
                self.source.refresh()
                before = time.monotonic()
                status = self.source.get('status')
                received = time.monotonic()
                row.update(connected=bool(status.get('connected')),telemetry=status,
                           status_request_ms=round((received-before)*1000,1),
                           line_received_monotonic=received,
                           line=self.line.update(status,received),error=None)
                camera = self.source.get('camera/status')
                row['camera_source']=camera
                if camera.get('valid') and camera.get('running'):
                    frame,seq = self.source.get('camera/frame',True)
                    frame_received = time.monotonic()
                    checked = self.source.get('camera/status')
                    key = (seq,checked.get('resolution'),checked.get('source'))
                    # Avoid renewing a duplicated frame's lifetime. A seq mismatch is
                    # conservatively rejected rather than claiming capture synchrony.
                    if not checked.get('valid') or str(checked.get('seq')) != seq:
                        row['vision_wait'] = '取帧时序变化，等待下一帧'
                    elif key == last_key:
                        row['vision_wait'] = '等待新画面，旧结果不续期'
                    else:
                        decode_start=time.monotonic()
                        image = cv.imdecode(np.frombuffer(frame,np.uint8),cv.IMREAD_COLOR)
                        if image is None: raise ValueError('JPEG decode failed')
                        decode_ms=(time.monotonic()-decode_start)*1000
                        self.vision.face_enabled=self.tracker.mode=='face'
                        vision,drawn = self.vision.process(image,frame_received)
                        age = checked.get('age_ms')
                        if type(age) not in (int,float) or not math.isfinite(age) or age<0:
                            raise ValueError('Missing source frame age')
                        total_age = age+(time.monotonic()-frame_received)*1000
                        tracking=self.tracker.update(vision,image.shape[1],image.shape[0],total_age)
                        if tracking['bbox'] is not None:
                            x,y,w,h=map(round,tracking['bbox'])
                            cv.rectangle(drawn,(x,y),(x+w,y+h),(255,220,70),2)
                            cv.line(drawn,(image.shape[1]//2,image.shape[0]//2),(x+w//2,y+h//2),(255,220,70),1)
                            cv.putText(drawn,f"TRACK {tracking['track_id']}",(x,max(18,y-8)),cv.FONT_HERSHEY_SIMPLEX,.55,(255,220,70),2)
                        tag_ids = tuple(t['id'] for t in vision['tags'])
                        tag_streak = tag_streak+1 if tag_ids and tag_ids==last_tag else (1 if tag_ids else 0)
                        last_tag = tag_ids
                        vision['tag_confirmation_frames'] = tag_streak
                        ok,jpeg = cv.imencode('.jpg',drawn,[cv.IMWRITE_JPEG_QUALITY,82])
                        if not ok: raise ValueError('Result JPEG encoding failed')
                        total_age=age+(time.monotonic()-frame_received)*1000
                        row.update(vision=vision if total_age<1500 else None,
                                   vision_valid=total_age<1500,source_age_ms=round(total_age),
                                   frame_seq=seq,frame_received_monotonic=frame_received,
                                   capture_timestamp_verified=False,
                                   tracking=tracking,decode_ms=round(decode_ms,2),
                                   cycle_ms=round((time.monotonic()-start)*1000,1))
                        last_key = key
                        with self.lock:
                            self.image = jpeg.tobytes()
                            self.image_at = time.monotonic()
                            self.image_seq=str(seq)
                            self.image_source_at=frame_received-age/1000
                            self.detection_times.append(self.image_at)
                        times=self.detection_times
                        row['detection_fps']=round((len(times)-1)/(times[-1]-times[0]),1) if len(times)>1 and times[-1]>times[0] else None
                        self.events.observe(vision,tracking,frame,jpeg.tobytes(),seq,total_age)
                        if row['vision_valid']:record_frame = frame
                else:
                    row['vision_wait']='外接相机没有新鲜画面'
                # Re-read independently aged telemetry after slow vision work.
                # Processing an image must not make a stale line look fresh.
                if time.monotonic()-received>.15:
                    current=self.source.get('status');line_received=time.monotonic()
                    row.update(telemetry=current,connected=bool(current.get('connected')),
                               line=self.line.update(current,line_received),line_received_monotonic=line_received)
            except Exception as error:
                row.update(connected=False,line=None,error=str(error),vision=None,vision_valid=False)
                self.line.previous=None
            if start<self.record_until and start-self.last_recorded>=1 and self.record_bytes<120*1024*1024:
                if record_frame:
                    name = f'frame-{self.recorded:05d}.jpg'
                    (self.session/name).write_bytes(record_frame)
                    row['raw_frame'] = name
                    self.record_bytes+=len(record_frame)
                row['label_note'] = '关联了人工/主控状态；相机固定、运动标签和严格同步尚未验收'
                self.journal.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
                self.journal.flush()
                self.recorded+=1; self.last_recorded=start
            with self.lock:
                if row.get('vision_wait') and self.data.get('vision'):
                    for name in ('vision','vision_valid','source_age_ms','frame_seq','tracking','detection_fps','cycle_ms'):
                        if name in self.data:row[name]=self.data[name]
                row['updated_monotonic']=time.monotonic()
                self.data = row
            self.quit.wait(.003 if self.local_camera else .03)
        self.journal.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8796)
    parser.add_argument('--record-seconds',type=int,default=60)
    cameras=parser.add_mutually_exclusive_group()
    cameras.add_argument('--borrowed-camera',action='store_true')
    cameras.add_argument('--original-camera',action='store_true')
    args=parser.parse_args()
    if not 0<=args.record_seconds<=600: parser.error('record-seconds must be 0..600')
    OUT.mkdir(parents=True,exist_ok=True)
    lab=Lab(args.record_seconds,args.borrowed_camera,args.original_camera)
    class Handler(BaseHTTPRequestHandler):
        def send(self,code,data,kind):
            self.send_response(code)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers();self.wfile.write(data)
        def do_GET(self):
            path=self.path.split('?',1)[0]
            if path=='/': self.send(200,(HERE/'index.html').read_bytes(),'text/html; charset=utf-8')
            elif path=='/app.js':self.send(200,(HERE/'app.js').read_bytes(),'text/javascript; charset=utf-8')
            elif path=='/labels':
                labels=json.loads((HERE.parent/'phone_vision/coco-labels-cn.json').read_text(encoding='utf-8'))
                self.send(200,json.dumps([x['cn'] for x in labels],ensure_ascii=False).encode('utf-8'),'application/json')
            elif path=='/api/status':self.send(200,json.dumps(lab.state(),ensure_ascii=False,allow_nan=False).encode('utf-8'),'application/json')
            elif path=='/api/events':self.send(200,json.dumps(lab.events.list(),ensure_ascii=False).encode('utf-8'),'application/json')
            elif path.startswith('/events/') and path.endswith('.jpg'):
                import re
                ident=path[len('/events/'):-4]
                if not re.fullmatch(r'event-\d{4}',ident):self.send(404,b'Not found','text/plain');return
                try:self.send(200,lab.events.image(ident),'image/jpeg')
                except ValueError:self.send(404,b'Not found','text/plain')
            elif path=='/frame.jpg':
                state=lab.state()
                with lab.lock: frame=lab.image
                if not state.get('vision_valid') or not frame:self.send(503,b'No fresh frame','text/plain')
                else:self.send(200,frame,'image/jpeg')
            elif path in ('/preview.mjpeg','/detection.mjpeg'):
                # This loop reads the capture thread directly. A slow detector
                # cannot hold the preview lock or force preview down to model FPS.
                preview=path=='/preview.mjpeg'
                if preview and not lab.local_camera:
                    self.send(409,b'Independent preview requires a selected local USB camera','text/plain');return
                self.send_response(200)
                self.send_header('Content-Type','multipart/x-mixed-replace; boundary=zhixingframe')
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.end_headers()
                previous=None;last=time.monotonic()
                try:
                    while not lab.quit.is_set():
                        if preview:frame,seq,source_at=lab.local_camera.snapshot()
                        else:
                            valid=lab.state().get('vision_valid')
                            with lab.lock:
                                frame,seq,source_at=(lab.image,lab.image_seq,lab.image_source_at) if valid else (None,None,None)
                        if frame is not None and seq!=previous:
                            head=(f'--zhixingframe\r\nContent-Type: image/jpeg\r\nContent-Length: {len(frame)}\r\nX-Frame-Seq: {seq}\r\nX-Source-Received-Ns: {int(source_at*1e9)}\r\n\r\n').encode('ascii')
                            self.wfile.write(head+frame+b'\r\n');self.wfile.flush()
                            previous=seq;last=time.monotonic()
                        elif time.monotonic()-last>2:break
                        lab.quit.wait(.005)
                except (BrokenPipeError,ConnectionResetError,OSError):pass
            else:self.send(404,b'Not found','text/plain')
        def do_POST(self):
            if self.path!='/api/tracking/config':self.send(405,b'Actuator endpoints are not exposed','text/plain');return
            if self.headers.get('Origin')!='http://'+self.headers.get('Host','') or self.headers.get('Content-Type','').split(';')[0]!='application/json':
                self.send(403,b'Use this local page','text/plain');return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=1024:raise ValueError('Invalid body size')
                result=lab.tracker.configure(json.loads(self.rfile.read(size)))
                self.send(200,json.dumps(result).encode('utf-8'),'application/json')
            except (ValueError,TypeError) as error:self.send(400,json.dumps({'error':str(error)}).encode('utf-8'),'application/json')
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    server.daemon_threads=True
    thread=threading.Thread(target=lab.worker,daemon=True);thread.start()
    runtime=dict(pid=os.getpid(),url=f'http://127.0.0.1:{args.port}/',session=str(lab.session),
                 started=timestamp(),actuation_enabled=False,borrowed_camera=args.borrowed_camera,
                 camera_kind='original' if args.original_camera else 'borrowed' if args.borrowed_camera else 'service')
    (OUT/'runtime.json').write_text(json.dumps(runtime,indent=2),encoding='utf-8')
    print(json.dumps(runtime),flush=True)
    try:server.serve_forever()
    finally:
        lab.quit.set();server.server_close();thread.join(timeout=6)
        if lab.local_camera:lab.local_camera.stop()

if __name__=='__main__': main()
