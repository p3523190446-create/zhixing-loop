"""Bounded latest-frame preview of the project's external 145F:02EC camera."""
from collections import deque
from pathlib import Path
import base64,re,shutil,subprocess,threading,time

RESOLUTIONS={'320x240':(320,240),'640x480':(640,480),'1280x720':(1280,720),'1920x1080':(1920,1080)}
FRAME_RATES=(5,10,15,20,30)
def settings(body):
    if not isinstance(body,dict) or set(body)-{'resolution','fps'}:raise ValueError('摄像头设置格式错误')
    resolution=body.get('resolution','640x480');fps=body.get('fps',15)
    if not isinstance(resolution,str) or resolution not in RESOLUTIONS or type(fps) is not int or fps not in FRAME_RATES:
        raise ValueError('请选择支持的分辨率和帧率')
    return resolution,fps
def jpeg_size(frame):
    at=2
    while at+4<=len(frame):
        if frame[at]!=255:return None
        while at<len(frame) and frame[at]==255:at+=1
        if at>=len(frame):return None
        marker=frame[at];at+=1
        if marker in (0xD9,0xDA):return None
        if marker in (0x01,*range(0xD0,0xD9)):continue
        if at+2>len(frame):return None
        size=int.from_bytes(frame[at:at+2],'big')
        if size<2 or at+size>len(frame):return None
        if marker in (0xC0,0xC1,0xC2,0xC3,0xC5,0xC6,0xC7,0xC9,0xCA,0xCB,0xCD,0xCE,0xCF):
            if size<7:return None
            return int.from_bytes(frame[at+5:at+7],'big'),int.from_bytes(frame[at+3:at+5],'big')
        at+=size
    return None

class CameraPreview:
    def __init__(self,folder):
        self.folder=Path(folder);self.lock=threading.Lock();self.operations=threading.Lock()
        self.proc=None;self.frame=None;self.frame_at=0;self.request_at=0
        self.seq=0;self.times=deque(maxlen=60);self.error=None;self.generation=0
        self.stop_event=threading.Event();self.reader=None;self.log=None
        self.resolution='640x480';self.requested_fps=15;self.dimensions_verified=False
        self.on_frame=None
        self.recording_status=None
        self.on_event=None
    def status(self):
        with self.lock:
            age=time.monotonic()-self.frame_at if self.frame_at else None
            live=self.proc is not None and self.proc.poll() is None
            fps=(len(self.times)-1)/(self.times[-1]-self.times[0]) if len(self.times)>1 and self.times[-1]>self.times[0] else 0
            return {'running':live,'valid':bool(live and age is not None and age<2),
                    'seq':self.seq,'age_ms':round(age*1000) if age is not None else None,
                    'fps':round(fps,1) if live else 0,'width':RESOLUTIONS[self.resolution][0],
                    'height':RESOLUTIONS[self.resolution][1],'resolution':self.resolution,
                    'requested_fps':self.requested_fps,'dimensions_verified':self.dimensions_verified,'device':'HDI Webcam USB',
                    'error':self.error,'source':'External USB 145F:02EC','recording':bool(self.recording_status and self.recording_status())}
    def latest_frame(self):
        with self.lock:
            self.request_at=time.monotonic()
            if self.proc is None or self.proc.poll() is not None or not self.frame_at or time.monotonic()-self.frame_at>=2:
                return None,self.seq
            return self.frame,self.seq
    def start(self,resolution='640x480',fps=15):
        settings({'resolution':resolution,'fps':fps})
        with self.operations:
            with self.lock:
                if self.proc and self.proc.poll() is None:
                    if self.resolution!=resolution or self.requested_fps!=fps:raise RuntimeError('请先关闭画面再切换设置')
                    return self.status_unlocked_running()
            executable=shutil.which('ffmpeg')
            if not executable:raise RuntimeError('未找到已安装的FFmpeg')
            # Bind the observed USB identity, never a camera index or the laptop webcam.
            found=subprocess.run([executable,'-hide_banner','-list_devices','true','-f','dshow','-i','dummy'],
                capture_output=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
            inventory=found.stderr.decode('utf-8',errors='replace')
            if self.on_event:self.on_event('camera_inventory',raw_stderr_b64=base64.b64encode(found.stderr).decode('ascii'))
            aliases=re.findall(r'Alternative name "([^"\r\n]*vid_145f&pid_02ec&mi_00[^"\r\n]*)"',inventory,re.I)
            if len(aliases)!=1:raise RuntimeError('未找到唯一的145F:02EC外接摄像头，请检查USB连接')
            log_name=f'camera-{time.time_ns()}.log';log=(self.folder/log_name).open('wb')
            args=[executable,'-hide_banner','-loglevel','error','-f','dshow','-rtbufsize','4M',
                  '-video_size',resolution,'-framerate',str(fps),'-vcodec','mjpeg','-i','video='+aliases[0],
                  '-an','-c:v','copy','-f','image2pipe','pipe:1']
            try:proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception:log.close();raise
            with self.lock:
                self.generation+=1;generation=self.generation;self.stop_event=threading.Event()
                self.proc=proc;self.log=log;self.frame=None;self.frame_at=0;self.seq=0;self.times.clear()
                self.request_at=time.monotonic();self.error=None;stop=self.stop_event
                self.resolution=resolution;self.requested_fps=fps;self.dimensions_verified=False
            if self.on_event:self.on_event('camera_started',resolution=resolution,requested_fps=fps,stderr_file=log_name)
            self.reader=threading.Thread(target=self.read,args=(proc,stop,generation,log,resolution,fps),daemon=True);self.reader.start()
            threading.Thread(target=self.watch,args=(proc,stop,generation),daemon=True).start()
            return {'running':True,'valid':False}
    def status_unlocked_running(self):return {'running':True}
    def read(self,proc,stop,generation,log,resolution,fps):
        pending=bytearray();next_publish=0;period=1/fps;first=True;last_capture=None;last_seq=0
        try:
            while not stop.is_set():
                chunk=proc.stdout.read(4096)
                if not chunk:break
                pending.extend(chunk)
                if len(pending)>2*1024*1024:raise RuntimeError('摄像头帧大小异常')
                while True:
                    start=pending.find(b'\xff\xd8')
                    if start<0:
                        if len(pending)>1:del pending[:-1]
                        break
                    end=pending.find(b'\xff\xd9',start+2)
                    if end<0:
                        if start:del pending[:start]
                        break
                    frame=bytes(pending[start:end+2]);del pending[:end+2]
                    if jpeg_size(frame)!=RESOLUTIONS[resolution]:raise RuntimeError('实际画面分辨率与选择不一致，已停止取流')
                    now=time.monotonic()
                    if now<next_publish:continue
                    next_publish=now+period if next_publish==0 or now-next_publish>period else next_publish+period
                    with self.lock:
                        if generation!=self.generation or stop.is_set():return
                        self.dimensions_verified=True
                        self.frame=frame;self.frame_at=time.monotonic();self.seq+=1;self.times.append(self.frame_at)
                        captured=self.frame_at;published_seq=self.seq
                    last_capture=int(captured*1e9);last_seq=published_seq
                    if first:
                        first=False
                        if self.on_event:self.on_event('camera_first_frame',generation=generation,captured_mono_ns=last_capture,frame_seq=published_seq,resolution=resolution)
                    if self.on_frame:self.on_frame(frame,captured,published_seq)
        except Exception as error:
            if self.on_event:self.on_event('camera_error',error=str(error))
            with self.lock:
                if generation==self.generation:self.error=str(error)
        finally:
            stop.set()
            if proc.poll() is None:proc.terminate()
            try:proc.wait(timeout=1)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=1)
            proc.stdout.close();log.close()
            with self.lock:
                if generation==self.generation:
                    self.proc=None;self.frame=None
                    if self.error is None:self.error='画面已停止；需要重新开启'
            if self.on_event:self.on_event('camera_reader_ended',generation=generation,last_capture_mono_ns=last_capture,last_seq=last_seq)
    def watch(self,proc,stop,generation):
        started=time.monotonic()
        while not stop.wait(.25):
            with self.lock:
                if generation!=self.generation:return
                now=time.monotonic();age=now-self.frame_at if self.frame_at else now-started
                reason='页面已离开，画面已停止' if now-self.request_at>10 else '摄像头画面中断，请检查USB连接' if age>(2 if self.frame_at else 7) else None
                if reason:self.error=reason
            if reason:
                if self.on_event:self.on_event('camera_timeout',reason=reason)
                stop.set()
                if proc.poll() is None:proc.terminate()
                return
    def stop(self):
        if self.on_event:self.on_event('camera_stop_requested')
        with self.operations:
            with self.lock:
                self.stop_event.set();proc=self.proc;reader=self.reader;self.frame=None;self.error='画面已关闭'
            if proc and proc.poll() is None:proc.terminate()
            if reader:reader.join(timeout=2)
        return {'running':False,'valid':False}
