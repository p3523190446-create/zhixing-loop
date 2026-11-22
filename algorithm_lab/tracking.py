"""Continuous target association and bounded pointing proposals.

The current USB031 is on the desk (user confirmed). No actuator I/O exists here.
Image axes must be physically mapped before proposals may become gimbal commands.
"""
import math,threading

def iou(a,b):
    x=max(a[0],b[0]);y=max(a[1],b[1])
    right=min(a[0]+a[2],b[0]+b[2]);bottom=min(a[1]+a[3],b[1]+b[3])
    overlap=max(0,right-x)*max(0,bottom-y)
    return overlap/max(1,a[2]*a[3]+b[2]*b[3]-overlap)

class TargetTracker:
    MODES=('red','green','blue','person','face','tag')
    def __init__(self):
        self.lock=threading.Lock();self.mode='red';self.enabled=True
        self.box=None;self.track_id=0;self.count=0;self.missed=0

    def configure(self,body):
        if not isinstance(body,dict) or set(body)-{'mode','enabled'}:raise ValueError('跟踪设置格式错误')
        mode=body.get('mode',self.mode);enabled=body.get('enabled',self.enabled)
        if mode not in self.MODES or type(enabled) is not bool:raise ValueError('请选择有效的跟踪目标')
        with self.lock:
            self.mode,self.enabled=mode,enabled
            self.box=None;self.count=0;self.missed=0
        return dict(mode=mode,enabled=enabled,actuation_enabled=False)

    def update(self,vision,width,height,age_ms):
        with self.lock:
            d=dict(mode=self.mode,enabled=self.enabled,state='SEARCHING',track_id=self.track_id,
                bbox=None,error_x=None,error_y=None,pointing_request=None,actuation_enabled=False,
                axis_mapping_verified=False,gimbal_reason='相机安装和云台方向尚未标定；当前只运行跟踪计算')
            if not self.enabled:return dict(d,state='PAUSED')
            if not isinstance(age_ms,(int,float)) or not math.isfinite(age_ms) or not 0<=age_ms<250:
                self.box=None;self.count=0;return dict(d,state='STALE')
            candidates=[]
            if self.mode in ('red','green','blue'):
                candidates=[c['bbox'] for c in vision.get('colors',[]) if c['color']==self.mode]
            elif self.mode=='person':
                candidates=[c['bbox'] for c in vision.get('objects',[]) if c['class_id']==0 and c['score']>=.5]
            elif self.mode=='face':
                candidates=[c['bbox'] for c in vision.get('faces',[]) if c['score']>=.85]
            elif self.mode=='tag':
                for tag in vision.get('tags',[]):
                    xs=[p[0] for p in tag['corners']];ys=[p[1] for p in tag['corners']]
                    candidates.append([min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys)])
            candidates=[b for b in candidates if len(b)==4 and all(math.isfinite(v) for v in b) and b[2]>0 and b[3]>0]
            if not candidates:
                self.missed+=1;self.count=0
                if self.missed>=3:self.box=None
                return dict(d,state='LOST' if self.box is not None else 'SEARCHING')
            if self.box is not None:
                chosen=max(candidates,key=lambda b:iou(self.box,b))
                distance=math.hypot((chosen[0]+chosen[2]/2-self.box[0]-self.box[2]/2)/width,
                                    (chosen[1]+chosen[3]/2-self.box[1]-self.box[3]/2)/height)
                same=iou(self.box,chosen)>.05 or distance<.2
            else:chosen=max(candidates,key=lambda b:b[2]*b[3]);same=False
            if not same:self.track_id+=1;self.count=0
            self.box=list(chosen);self.missed=0;self.count+=1
            x=(chosen[0]+chosen[2]/2)/(width/2)-1
            y=(chosen[1]+chosen[3]/2)/(height/2)-1
            x=max(-1.,min(1.,x));y=max(-1.,min(1.,y))
            def correction(error):return 0. if abs(error)<.08 else max(-.5,min(.5,error*.5))
            return dict(d,state='TRACKING' if self.count>=3 else 'LOCKING',track_id=self.track_id,
                bbox=chosen,error_x=x,error_y=y,consistent_frames=self.count,
                pointing_request=dict(image_x=correction(x),image_y=correction(y)) if self.count>=3 else None)
