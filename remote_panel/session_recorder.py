"""Timestamped JPEG video plus received MCU state, bounded and replayable."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,queue,re,secrets,shutil,threading,time,os
ID=re.compile(r'\d{8}-\d{6}-[0-9a-f]{6}\Z')
class Recorder:
    def __init__(self,folder):
        self.root=Path(folder);self.root.mkdir(parents=True,exist_ok=True)
        self.lock=threading.Lock();self.operation=threading.Lock();self.active=False;self.finishing=False
        self.id=None;self.started=0;self.frames=0;self.samples=0;self.bytes=0;self.dropped=0
        self.reason=None;self.error=None;self.duration=0;self.thread=None;self.source=None
        self.cache={}
    def status(self):
        with self.lock:return {'active':self.active,'finishing':self.finishing,'id':self.id,
            'duration_s':round(time.monotonic()-self.started if self.active or self.finishing else self.duration,1),
            'frames':self.frames,'samples':self.samples,'bytes':self.bytes,'dropped_frames':self.dropped,
            'reason':self.reason,'error':self.error,'max_seconds':600,'max_bytes':512*1024*1024}
    def start(self,source):
        with self.operation:
            if self.status()['active'] or self.status()['finishing']:raise ValueError('正在记录或保存，请稍等')
            initial=source()
            if not initial.get('camera',{}).get('valid'):raise ValueError('请先开启有效的摄像头画面')
            if not initial.get('connected'):raise ValueError('请先连接主控，再开始同步记录')
            if shutil.disk_usage(self.root).free<64*1024*1024:raise ValueError('剩余磁盘空间不足')
            sid=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d-%H%M%S-')+secrets.token_hex(3)
            folder=self.root/sid;folder.mkdir()
            with self.lock:
                self.id=sid;self.started=time.monotonic();self.frames=self.samples=self.bytes=self.dropped=0
                self.reason=self.error=None;self.duration=0;self.source=source;self.q=queue.Queue(maxsize=32)
                self.end=threading.Event();self.active=True;self.finishing=False
                self.initial={'id':sid,'started_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
                    'camera':initial['camera'],'state':'RECORDING','sync':'PC monotonic reception time; MCU sample ages retained',
                    'pc_origin_monotonic_ns':int(self.started*1e9),'diagnostic_run':initial.get('diagnostics'),
                    'format':'JPEG stream with frame timestamp/offset index and JSONL telemetry; no audio'}
            try:(folder/'session.json').write_text(json.dumps(self.initial,ensure_ascii=False,indent=2),encoding='utf-8')
            except OSError as error:
                with self.lock:self.active=False;self.error=str(error)
                raise
            self.thread=threading.Thread(target=self.run,args=(folder,),daemon=True);self.thread.start()
            return self.status()
    def on_frame(self,frame,captured,seq):
        with self.lock:
            if not self.active:return
            try:self.q.put_nowait((frame,captured,seq))
            except queue.Full:self.dropped+=1
    def request_stop(self,reason):
        with self.lock:
            if self.active:self.active=False;self.finishing=True;self.reason=reason;self.end.set()
    def stop(self,reason='用户停止'):
        with self.operation:
            self.request_stop(reason)
            if self.thread:self.thread.join(timeout=3)
            return self.status()
    def run(self,folder):
        offset=0;next_sample=0;last_key=None;last_flush=0
        try:
            with (folder/'video.mjpeg').open('wb') as video,(folder/'frames.jsonl').open('w',encoding='utf-8') as index,(folder/'telemetry.jsonl').open('w',encoding='utf-8') as journal:
                while not self.end.is_set() or not self.q.empty():
                    now=time.monotonic()
                    if not self.end.is_set() and now>=next_sample:
                        data=self.source();now=time.monotonic();next_sample=now+.25
                        key=(data.get('received_at'),data.get('connected'),(data.get('gimbal') or {}).get('ms'))
                        if key!=last_key:
                            row={'t':round(now-self.started,6),'state':data}
                            journal.write(json.dumps(row,ensure_ascii=False)+'\n');self.samples+=1;last_key=key
                        if not data.get('camera',{}).get('valid'):self.request_stop('摄像头画面中断')
                        if now-self.started>=600:self.request_stop('达到10分钟上限')
                        if shutil.disk_usage(self.root).free<32*1024*1024:self.request_stop('磁盘空间不足')
                    try:frame,captured,seq=self.q.get(timeout=.05)
                    except queue.Empty:continue
                    if self.bytes+len(frame)>512*1024*1024:
                        self.request_stop('达到512MB上限');self.dropped+=1;continue
                    video.write(frame)
                    index.write(json.dumps({'t':round(max(0,captured-self.started),6),'offset':offset,'length':len(frame),'seq':seq})+'\n')
                    offset+=len(frame);self.frames+=1;self.bytes=offset
                    if now-last_flush>=1:
                        video.flush();index.flush();journal.flush();last_flush=now
                for stream in (video,index,journal):stream.flush();os.fsync(stream.fileno())
        except Exception as error:
            with self.lock:self.error=str(error)
            self.request_stop('写入失败')
        finally:
            with self.lock:
                self.active=False;self.duration=time.monotonic()-self.started
                final={**self.initial,**self.status_unlocked(),'state':'ERROR' if self.error else 'COMPLETE'}
            try:
                tmp=folder/'session.tmp';tmp.write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(tmp,folder/'session.json')
            except Exception as error:
                with self.lock:self.error=str(error)
            with self.lock:self.finishing=False
    def status_unlocked(self):return {'duration_s':round(self.duration,3),'frames':self.frames,'samples':self.samples,'bytes':self.bytes,'dropped_frames':self.dropped,'reason':self.reason,'error':self.error}
    def folder(self,sid):
        if not ID.fullmatch(sid):raise ValueError('记录编号无效')
        path=(self.root/sid).resolve()
        if path.parent!=self.root.resolve() or not path.is_dir():raise ValueError('记录不存在')
        return path
    def sessions(self):
        result=[]
        for folder in sorted(self.root.iterdir(),reverse=True):
            if not folder.is_dir() or not ID.fullmatch(folder.name):continue
            try:
                meta=json.loads((folder/'session.json').read_text(encoding='utf-8'))
                if meta.get('state')=='RECORDING' and folder.name!=self.id:meta['state']='INTERRUPTED'
                result.append(meta)
            except (OSError,ValueError):continue
            if len(result)>=100:break
        return result
    def replay(self,sid):
        folder=self.folder(sid)
        if sid==self.id and (self.active or self.finishing):raise ValueError('请先停止并保存记录')
        with self.lock:
            if sid in self.cache:return self.cache[sid]
        def rows(name):
            found=[]
            with (folder/name).open(encoding='utf-8') as f:
                for line in f:
                    try:found.append(json.loads(line))
                    except ValueError:break
            return found
        meta=json.loads((folder/'session.json').read_text(encoding='utf-8'))
        frames=rows('frames.jsonl');samples=rows('telemetry.jsonl')
        result={'meta':meta,'frames':frames,'samples':samples}
        with self.lock:
            if len(self.cache)>=3:self.cache.pop(next(iter(self.cache)))
            self.cache[sid]=result
        return result
    def frame(self,sid,position):
        data=self.replay(sid);frames=data['frames']
        if position<0 or position>=len(frames):raise ValueError('帧编号无效')
        row=frames[position]
        if not 0<row['length']<=2*1024*1024:raise ValueError('帧数据异常')
        with (self.folder(sid)/'video.mjpeg').open('rb') as f:f.seek(row['offset']);frame=f.read(row['length'])
        if len(frame)!=row['length'] or not frame.startswith(b'\xff\xd8') or not frame.endswith(b'\xff\xd9'):raise ValueError('帧不完整')
        return frame
