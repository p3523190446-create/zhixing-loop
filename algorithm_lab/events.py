"""Bounded local event photographs; no network uploads or automatic motion."""
from pathlib import Path
import datetime,json,threading,time

class EventStore:
    def __init__(self,folder):
        self.folder=folder/'events';self.folder.mkdir(exist_ok=True)
        self.lock=threading.Lock();self.items=[];self.last=0
        self.motion=False;self.tracked=False;self.tags=()
        self.mode=None
    def observe(self,vision,tracking,raw,annotated,seq,age_ms):
        now=time.monotonic();reason=None
        tracked=tracking.get('state')=='TRACKING'
        motion=bool(vision.get('motion_event'))
        tags=tuple(t['id'] for t in vision.get('tags',[])) if vision.get('tag_confirmation_frames',0)>=3 else ()
        if tracked and not self.tracked:reason='target_acquired'
        elif self.tracked and not tracked:
            reason='target_lost' if tracking.get('state')=='LOST' and tracking.get('mode')==self.mode else 'tracking_ended'
        elif tags and tags!=self.tags:reason='marker_seen'
        elif motion and not self.motion:reason='scene_changed'
        self.tracked,self.motion,self.tags=tracked,motion,tags
        self.mode=tracking.get('mode')
        if not reason or now-self.last<3 or len(self.items)>=50 or age_ms>=500:return
        ident=f'event-{len(self.items)+1:04d}'
        data=dict(id=ident,reason=reason,at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
                  frame_seq=seq,source_age_ms=age_ms,tracking=tracking,tags=list(tags),
                  motion_note='画面变化可能来自镜头移动或光照，不等于已确认有人移动',actuation_enabled=False)
        (self.folder/(ident+'-raw.jpg')).write_bytes(raw)
        (self.folder/(ident+'.jpg')).write_bytes(annotated)
        (self.folder/(ident+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        with self.lock:self.items.append(data);self.last=now
    def list(self):
        with self.lock:return list(reversed(self.items[-12:]))
    def image(self,ident):
        with self.lock:
            if not any(x['id']==ident for x in self.items):raise ValueError('记录不存在')
        return (self.folder/(ident+'.jpg')).read_bytes()
