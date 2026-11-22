"""Always-on byte-exact host UART journal; rotations never discard older segments."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import base64,json,threading,time,os,secrets
class DiagnosticJournal:
    def __init__(self,root):
        self.root=Path(root);self.id=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d-%H%M%S-')+secrets.token_hex(3)
        self.folder=self.root/self.id;self.folder.mkdir(parents=True)
        self.lock=threading.Lock();self.seq=0;self.segment=0;self.bytes=0;self.error=None
        self.started_ns=time.monotonic_ns();self.last_sync=0;self.stream=None
        self._open()
        (self.folder/'manifest.json').write_text(json.dumps({'id':self.id,'started_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
            'clock':'PC monotonic_ns','origin_monotonic_ns':self.started_ns,'source':'HOST_USB_UART_VISIBLE_BYTES',
            'raw_encoding':'base64, exact bytes including delimiters and invalid text',
            'coverage':'Host attempted writes, accepted writes, received bytes, UI actions, connection/errors. MCU internal untransmitted events are not captured.',
            'rotation_bytes':16*1024*1024,'automatic':True},ensure_ascii=False,indent=2),encoding='utf-8')
        self.event('logger_started')
    def _open(self):
        if self.stream:self.stream.flush();os.fsync(self.stream.fileno());self.stream.close()
        self.stream=(self.folder/f'events-{self.segment:04d}.jsonl').open('ab');self.segment+=1;self.bytes=0
    def status(self):
        with self.lock:return {'id':self.id,'ok':self.error is None,'error':self.error,'seq':self.seq,'segments':self.segment,'automatic':True}
    def event(self,event,**fields):
        with self.lock:
            if self.error:return False
            try:
                now=time.monotonic_ns();self.seq+=1
                row={**fields,'seq':self.seq,'mono_ns':now,'t':(now-self.started_ns)/1e9,'event':event}
                payload=(json.dumps(row,ensure_ascii=False)+'\n').encode('utf-8')
                if self.bytes+len(payload)>16*1024*1024:self._open()
                self.stream.write(payload);self.bytes+=len(payload);self.stream.flush()
                if now-self.last_sync>=1_000_000_000:os.fsync(self.stream.fileno());self.last_sync=now
                return True
            except Exception as error:self.error=str(error);return False
    def raw(self,direction,content,**fields):
        return self.event('uart_bytes',direction=direction,length=len(content),data_b64=base64.b64encode(content).decode('ascii'),**fields)
    def close(self):
        self.event('logger_closed')
        with self.lock:
            if self.stream:
                try:self.stream.flush();os.fsync(self.stream.fileno());self.stream.close()
                except Exception as error:self.error=str(error)
