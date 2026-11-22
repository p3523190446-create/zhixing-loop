"""Ownership, stale requests, invalid positions and lease loss; mock UART only."""
from pathlib import Path
import json,tempfile,time
from gimbal_controls import Controls,Request,pulse_targets

def main():
    with tempfile.TemporaryDirectory() as folder:
        c=Controls(Path(folder));sent=[]
        g=dict(ms=1000,ready=1,active=0,mode=0,yaw_us=0,pitch_us=0,starts=0,stops=0,yaw_hz=1000000,pitch_hz=1000000)
        def exchange(command,prefix):
            sent.append(command)
            if command=='GIMBAL_MANUAL_START':g.update(active=1,mode=5,yaw_us=1500,pitch_us=1500,starts=g['starts']+1)
            if command=='GIMBAL_STOP':g.update(active=0,yaw_us=0,pitch_us=0,stops=g['stops']+1)
            return prefix
        def state():g['ms']+=1;return dict(g)
        def request(action,body,deadline=None):
            r=Request(action,body,time.monotonic()+1 if deadline is None else deadline)
            c.queue.put((0,next(c.counter),r));c.service(exchange,state);assert r.done.is_set();return r
        assert pulse_targets(-100,100)==(1300,1650)
        assert pulse_targets(100,-100)==(1700,1350)
        for x,y in ((101,0),(0,-101),(True,0),(0,False),(1.5,0),('0',0)):
            before=len(sent);code,_=c.submit('set',{'yaw':x,'pitch':y});assert code==400 and len(sent)==before
        r=request('start',{},time.monotonic()-1);assert r.code==503 and 'GIMBAL_MANUAL_START' not in sent
        r=request('heartbeat',{'session':'unknown'});assert r.code==409 and not g['active']
        r=request('start',{});assert r.code==200 and c.owner and g['active']
        owner=r.response['session'];count=sent.count('GIMBAL_MANUAL_START')
        r=request('start',{});assert r.code==409 and sent.count('GIMBAL_MANUAL_START')==count
        r=request('set',{'session':'other','yaw':50,'pitch':50});assert r.code==409 and not any(s.startswith('GIMBAL_SET') for s in sent)
        r=request('set',{'session':owner,'yaw':50,'pitch':-50});assert r.code==200 and 'GIMBAL_SET,1600,1425' in sent
        c.last_touch=time.monotonic()-2;c.service(exchange,state);assert c.owner is None and not g['active']
        r=request('heartbeat',{'session':owner});assert r.code==409 and not g['active']
        r=request('start',{});assert r.code==200
        r=request('stop',{});assert r.response['stopped'] and not c.owner and g['yaw_us']==g['pitch_us']==0
        late=Request('start',{},time.monotonic()+1);stop=Request('stop',{},time.monotonic()+1)
        c.queue.put((1,next(c.counter),late));c.queue.put((0,next(c.counter),stop))
        c.service(exchange,state);assert stop.code==200 and late.code==503 and not g['active']
        result={'result':'OWNERSHIP_STALE_INVALID_TARGET_LEASE_STOP_PASS','hardware_access':'NONE'}
        (Path(__file__).parent/'manual-controls-host-check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(result['result'])
if __name__=='__main__':main()
