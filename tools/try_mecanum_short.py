"""Explicitly requested low-speed MCU-controlled pulses; always request STOP."""
from pathlib import Path
import argparse,json,time,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'output/onboard_dashboard/mecanum-live-20261107'
def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--limit',type=int,default=10);p.add_argument('--duration',type=float,default=.35);p.add_argument('--forward-only',action='store_true');p.add_argument('--lateral-only',action='store_true');a=p.parse_args()
 assert not (a.forward_only and a.lateral_only)
 assert 1<=a.limit<=20 and 0<a.duration<=.8,'This trial is limited to 20 percent / 800ms'
 if not a.execute:print('No motion; use --execute only for the user-authorized trial');return
 cfg=json.loads((ROOT/'output/onboard_dashboard/pc-speed-20261021/runtime.json').read_text(encoding='utf-8-sig'));origin='http://127.0.0.1:8795'
 def call(path,body=None):
  request=urllib.request.Request(origin+cfg['base']+'/api/'+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json','Origin':origin})
  try:
   with urllib.request.urlopen(request,timeout=2) as r:return json.load(r)
  except urllib.error.HTTPError as e:raise RuntimeError(str(e.code)+' '+e.read().decode()) from e
 def state():
  d=call('status');return {k:d.get(k) for k in ('connected','firmware','voltage_mv','wheel_speeds','speed_targets','speed_commands','drive','controller_fault','age_ms','capabilities')}
 def stop():
  failure=None
  for _ in range(5):
   try:
    response=call('drive/stop',{});assert response.get('stopped') is True
    for _ in range(15):
     s=state()
     if s['connected'] and not s['drive']['active'] and not s['drive']['moving'] and all(v==0 for v in s['speed_targets']+s['speed_commands']) and all(abs(v)<=8 for v in s['wheel_speeds']):return s
     time.sleep(.1)
    raise RuntimeError('No zero feedback confirmation')
   except Exception as e:failure=e;time.sleep(.1)
  raise failure
 report={'scope':'real encoder/command response only; body direction not visually verified','limit_percent':a.limit,'single_vector_ms':round(a.duration*1000),'pulses':[],'body_direction_verified':False}
 initial=state();assert initial['connected'] and initial['firmware']=='R1_DRIVE_STARTUP_MANUAL_MECANUM_V2_20261107'
 assert initial['capabilities'].get('mecanum_control') is True
 assert not initial['drive']['active'] and all(v==0 for v in initial['speed_targets']+initial['speed_commands'])
 try:
  directions=[('forward',100,0,0)] if a.forward_only else [('right',0,100,0),('left',0,-100,0),('clockwise',0,0,100)] if a.lateral_only else [('forward',100,0,0),('right',0,100,0),('left',0,-100,0),('clockwise',0,0,100)]
  if a.lateral_only:report['wheel_load']='SUSPENDED_USER_CONFIRMED'
  for name,f,x,r in directions:
   before=stop();assert 6000<=before['voltage_mv']<=8500
   armed=call('drive/start',{'mode':'manual'});sid=armed['session']
   item={'name':name,'before':before,'samples':[]};report['pulses'].append(item)
   began=time.monotonic()
   try:
    seq=1;call('drive/set',dict(session=sid,seq=seq,throttle=f,strafe=x,turn=r,limit=a.limit));last_send=time.monotonic()
    item['accepted']=True
    while time.monotonic()-began<a.duration:
     if time.monotonic()-last_send>=.12:
      seq+=1;call('drive/set',dict(session=sid,seq=seq,throttle=f,strafe=x,turn=r,limit=a.limit));last_send=time.monotonic()
     sample=state();item['samples'].append(sample)
     if not sample['connected'] or sample.get('controller_fault'):raise RuntimeError('Feedback disconnected or controller tripped')
     time.sleep(.04)
   finally:item['after']=stop();item['elapsed_including_stop_ms']=round((time.monotonic()-began)*1000)
   print(json.dumps({'pulse':name,'accepted':item.get('accepted',False),'stopped':not item['after']['drive']['active'],'observed_speeds':[s['wheel_speeds'] for s in item['samples']]},ensure_ascii=False),flush=True)
   # A real controller trip ends this trial; never automatically re-arm a fault.
   if item['after'].get('controller_fault'):raise RuntimeError('Controller fault '+str(item['after']['controller_fault']))
   time.sleep(.6)
  report['result']='PULSES_SENT_AND_ZERO_CONFIRMED'
 except Exception as e:report['result']='STOPPED_ON_ERROR';report['error']=str(e);raise
 finally:
  try:report['final']=stop()
  finally:
   name='physical-forward-20pct.json' if a.forward_only else 'physical-suspended-lateral-20pct.json' if a.lateral_only else 'physical-pulses.json'
   (OUT/name).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
