"""Explicit desktop USB camera profiles, with no integrated-camera fallback.

Borrowed USB031: 1920x1536 UYVY resized to 960x768.
Original 145F:02EC: native 640x480 MJPEG passed through without re-encoding.
"""
import bootstrap
import re,shutil,subprocess,threading,time
from collections import deque
import cv2 as cv
import numpy as np

class BorrowedCamera:
    def __init__(self,folder,kind='borrowed'):
        if kind not in ('original','borrowed'):raise ValueError('Unknown camera profile')
        self.kind=kind
        self.width,self.height=(640,480) if kind=='original' else (960,768)
        self.identity='145F:02EC' if kind=='original' else '04B4:00C3'
        self.source=('Original car camera ' if kind=='original' else 'Borrowed USB031 ')+self.identity
        self.folder=folder
        self.lock=threading.Lock();self.quit=threading.Event()
        self.proc=None;self.reader=None;self.frame=None;self.at=0;self.seq=0
        self.error=None;self.log=None
        self.times=deque(maxlen=60)

    def start(self):
        executable=shutil.which('ffmpeg')
        if not executable:raise RuntimeError('FFmpeg is not installed')
        found=subprocess.run([executable,'-hide_banner','-list_devices','true','-f','dshow','-i','dummy'],
            capture_output=True,timeout=8,creationflags=subprocess.CREATE_NO_WINDOW)
        (self.folder/(self.kind+'-camera-inventory.log')).write_bytes(found.stderr)
        inventory=found.stderr.decode('utf-8',errors='replace')
        vid,pid=self.identity.lower().split(':')
        aliases=re.findall(r'Alternative name "([^"\r\n]*vid_'+vid+r'&pid_'+pid+r'&mi_00[^"\r\n]*)"',inventory,re.I)
        if len(aliases)!=1:raise RuntimeError('未发现唯一的所选USB摄像头 '+self.identity+'；不会改用其他相机')
        options=subprocess.run([executable,'-hide_banner','-list_options','true','-f','dshow','-i','video='+aliases[0]],
            capture_output=True,timeout=8,creationflags=subprocess.CREATE_NO_WINDOW)
        (self.folder/(self.kind+'-camera-modes.log')).write_bytes(options.stderr)
        pattern=(rb'vcodec=mjpeg\s+min s=640x480 fps=[0-9.]+ max s=640x480 fps=30' if self.kind=='original'
                 else rb'pixel_format=uyvy422\s+min s=1920x1536 fps=30')
        if not re.search(pattern,options.stderr):
            raise RuntimeError('所选相机支持格式改变；未套用旧设置')
        self.log=(self.folder/(self.kind+'-camera-ffmpeg.log')).open('wb')
        native=['-video_size','640x480','-framerate','30','-vcodec','mjpeg'] if self.kind=='original' else ['-video_size','1920x1536','-framerate','30','-pixel_format','uyvy422']
        output=['-c:v','copy'] if self.kind=='original' else ['-vf','scale=960:768:flags=fast_bilinear','-c:v','mjpeg','-q:v','5','-threads','2']
        args=[executable,'-hide_banner','-loglevel','warning','-fflags','nobuffer',
              '-thread_queue_size','1','-f','dshow','-rtbufsize','12M',
              *native,'-i','video='+aliases[0],'-an',*output,'-f','image2pipe','pipe:1']
        self.proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=self.log,creationflags=subprocess.CREATE_NO_WINDOW)
        self.reader=threading.Thread(target=self.read,daemon=True);self.reader.start()

    def status(self):
        with self.lock:
            running=self.proc is not None and self.proc.poll() is None
            age=round((time.monotonic()-self.at)*1000) if self.at else None
            observed_fps=(len(self.times)-1)/(self.times[-1]-self.times[0]) if len(self.times)>1 and self.times[-1]>self.times[0] else None
            return dict(running=running,valid=bool(running and age is not None and age<1500),
                seq=self.seq,age_ms=age,width=self.width,height=self.height,resolution=f'{self.width}x{self.height}',
                requested_fps=30,observed_fps=round(observed_fps,1) if observed_fps is not None else None,
                input_resolution='640x480' if self.kind=='original' else '1920x1536',
                input_format='MJPEG 30fps requested' if self.kind=='original' else 'UYVY422 30fps requested',
                source=self.source,camera_kind=self.kind,usb_identity=self.identity,
                preview_reencoded=self.kind!='original',error=self.error)

    def latest_frame(self):
        with self.lock:
            if not self.proc or self.proc.poll() is not None or not self.at or time.monotonic()-self.at>=1.5:
                return None,str(self.seq)
            return self.frame,str(self.seq)

    def snapshot(self):
        with self.lock:
            if not self.proc or self.proc.poll() is not None or not self.at or time.monotonic()-self.at>=1.5:
                return None,str(self.seq),None
            return self.frame,str(self.seq),self.at

    def read(self):
        pending=bytearray()
        try:
            while not self.quit.is_set():
                chunk=self.proc.stdout.read1(65536)
                if not chunk:break
                pending.extend(chunk)
                if len(pending)>8*1024*1024:raise ValueError('Borrowed camera frame exceeded bounded buffer')
                while True:
                    start=pending.find(b'\xff\xd8')
                    if start<0:
                        if len(pending)>1:del pending[:-1]
                        break
                    end=pending.find(b'\xff\xd9',start+2)
                    if end<0:
                        if start:del pending[:start]
                        break
                    data=bytes(pending[start:end+2]);del pending[:end+2]
                    image=cv.imdecode(np.frombuffer(data,np.uint8),cv.IMREAD_COLOR)
                    if image is None or image.shape[:2]!=(self.height,self.width):
                        raise ValueError('所选相机真实画面尺寸与选择不一致')
                    with self.lock:
                        self.frame=data;self.at=time.monotonic();self.seq+=1
                        self.times.append(self.at)
            if not self.quit.is_set():raise RuntimeError('所选相机取流结束；请检查USB数据连接')
        except Exception as error:
            with self.lock:self.error=str(error);self.frame=None;self.at=0
        finally:
            if self.proc.poll() is None:self.proc.terminate()
            try:self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:self.proc.kill()

    def stop(self):
        self.quit.set()
        if self.proc and self.proc.poll() is None:self.proc.terminate()
        if self.reader:self.reader.join(timeout=3)
        if self.proc and self.proc.stdout:self.proc.stdout.close()
        if self.log:self.log.close()
