"""Single-owner manual gimbal session, immutable serial commands, no vehicle writes."""
from dataclasses import dataclass,field
from datetime import datetime,timezone
import itertools,json,queue,secrets,threading,time

def pulse_targets(yaw,pitch):
    if type(yaw) is not int or type(pitch) is not int or not (-100<=yaw<=100 and -100<=pitch<=100):
        raise ValueError('位置必须是-100到100之间的整数')
    return round(1500+2*yaw),round(1500+1.5*pitch)

@dataclass
class Request:
    action:str
    body:dict
    deadline:float
    done:threading.Event=field(default_factory=threading.Event)
    response:dict=field(default_factory=dict)
    code:int=200

class Controls:
    def __init__(self,folder):
        self.folder=folder;self.lock=threading.Lock();self.queue=queue.PriorityQueue();self.counter=itertools.count()
        self.owner=None;self.last_touch=0;self.expected_starts=None;self.previous_ms=None
        self.events=[];self.target={'yaw':0,'pitch':0};self.state='STOPPED';self.error=None
    def public(self):
        with self.lock:
            return {'active':self.owner is not None,'state':self.state,'target':dict(self.target),
                    'error':self.error,'events':list(self.events[-8:])}
    def event(self,message):
        self.events.append({'at':datetime.now(timezone.utc).isoformat(),'message':message})
        self.events=self.events[-20:]
        with (self.folder/'control-events.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(self.events[-1],ensure_ascii=False)+'\n')
    def submit(self,action,body):
        if action not in ('start','set','center','heartbeat','stop'):
            return 404,{'error':'没有这个操作'}
        if not isinstance(body,dict):return 400,{'error':'请求格式错误'}
        if action=='set':
            try:pulse_targets(body.get('yaw'),body.get('pitch'))
            except ValueError as error:return 400,{'error':str(error)}
        request=Request(action,body,time.monotonic()+1.6)
        self.queue.put((0 if action=='stop' else 1,next(self.counter),request))
        if not request.done.wait(1.8):return 503,{'error':'主控暂未确认，控制将按超时停止'}
        return request.code,request.response
    def disconnect(self,error):
        with self.lock:
            if self.owner:self.event('通信中断，已取消控制；不会自动恢复')
            self.owner=None;self.expected_starts=None;self.previous_ms=None
            self.state='OFFLINE';self.error=str(error)
        self.reject_pending('主控未连接')
    def reject_pending(self,message):
        for _ in range(64):
            try:_,_,r=self.queue.get_nowait()
            except queue.Empty:return
            r.code=503;r.response={'error':message};r.done.set()
    def service(self,exchange,gimbal_snapshot):
        with self.lock:
            if self.owner and time.monotonic()-self.last_touch>=1.8:
                exchange('GIMBAL_STOP','GIMBAL_STOPPED')
                self.owner=None;self.expected_starts=None;self.state='STOPPED'
                self.event('页面连接中断，云台已停止')
        for _ in range(4):
            try:_,_,r=self.queue.get_nowait()
            except queue.Empty:break
            try:
                with self.lock:
                    if time.monotonic()>r.deadline:
                        r.code=503;r.response={'error':'请求已过期，请重新操作'}
                    elif r.action=='stop':
                        exchange('GIMBAL_STOP','GIMBAL_STOPPED')
                        final=gimbal_snapshot()
                        if final['active'] or final['yaw_us'] or final['pitch_us']:raise RuntimeError('主控未确认停止')
                        self.owner=None;self.expected_starts=None;self.state='STOPPED';self.error=None
                        self.reject_pending('停止已优先执行，请重新操作')
                        self.event('停止已由主控确认');r.response={'ok':True,'stopped':True}
                    elif r.action=='start':
                        if self.owner:r.code=409;r.response={'error':'已有页面正在控制，请先停止'}
                        else:
                            g=gimbal_snapshot()
                            if not g['ready'] or g['active']:raise RuntimeError('主控未就绪或已有其他控制')
                            exchange('GIMBAL_MANUAL_START','GIMBAL_MANUAL_STARTED')
                            self.owner=secrets.token_urlsafe(12);self.last_touch=time.monotonic()
                            self.expected_starts=g['starts']+1;self.previous_ms=g['ms']
                            self.target={'yaw':0,'pitch':0};self.state='MANUAL';self.error=None
                            self.event('手动控制已开启，回到中间位置')
                            r.response={'ok':True,'session':self.owner}
                    elif not self.owner or r.body.get('session')!=self.owner:
                        r.code=409;r.response={'error':'控制已停止，请重新开启'}
                    else:
                        if r.action in ('set','center'):
                            yaw,pitch=(0,0) if r.action=='center' else (r.body['yaw'],r.body['pitch'])
                            y,p=pulse_targets(yaw,pitch)
                            exchange(f'GIMBAL_SET,{y},{p}','GIMBAL_SET_ACCEPTED')
                            self.target={'yaw':yaw,'pitch':pitch}
                            self.event('位置已由主控接收' if r.action=='set' else '回中已由主控接收')
                        self.last_touch=time.monotonic();r.response={'ok':True,'target':dict(self.target)}
            except Exception as error:
                r.code=503;r.response={'error':str(error)};r.done.set();raise
            r.done.set()
        with self.lock:
            if self.owner:
                exchange('GIMBAL_KEEPALIVE','GIMBAL_ALIVE')
                g=gimbal_snapshot()
                if g['active']!=1 or g['mode']!=5 or g['starts']!=self.expected_starts or g['ms']<self.previous_ms:
                    raise RuntimeError('主控已停止或重启，请重新开启控制')
                self.previous_ms=g['ms']
                return g
        return None
