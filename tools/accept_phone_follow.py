"""Supervised phone/P7 acceptance. Only camera and gimbal APIs; never drives wheels."""
from pathlib import Path
import argparse,json,statistics,time,urllib.request
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--url');p.add_argument('--out',type=Path,default=ROOT/'output/onboard_dashboard/phone-standalone-20261107');p.add_argument('--color',choices=['red','green','blue'],default='red');p.add_argument('--seconds',type=int,default=20);p.add_argument('--execute',action='store_true');p.add_argument('--probe-only',action='store_true');p.add_argument('--skip-probes',action='store_true');p.add_argument('--initial-yaw',type=int,default=0);p.add_argument('--initial-pitch',type=int,default=0);p.add_argument('--probe-step',type=int,choices=[-5,-2,2,5],default=2);args=p.parse_args()
 assert -98<=args.initial_yaw<=98 and -98<=args.initial_pitch<=98,'初始位置超出试移范围'
 out=args.out;out.mkdir(parents=True,exist_ok=True)
 raw=args.url or json.loads((ROOT/'output/onboard_dashboard/large-vision-20261107/lan-source-private.json').read_text(encoding='utf-8'))['url']
 u=urlsplit(raw);base=u.scheme+'://'+u.netloc+'/'+u.path.split('/')[1];origin=u.scheme+'://'+u.netloc
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 def api(path,body=None):
  req=urllib.request.Request(base+'/api/'+path,data=None if body is None else json.dumps(body).encode(),headers={'Origin':origin,'Content-Type':'application/json'})
  try:return json.load(opener.open(req,timeout=1.2))
  except urllib.error.HTTPError as e:raise RuntimeError(json.load(e).get('error','API failed')) from e
 report={'scope':'PHONE_LOCAL_COLOR_CONTROL_WITH_SUPERVISED_WEB_LEASE','color':args.color,'physical_angle_feedback':False,'wheel_commands_sent':False,'axis_probes':[],'samples':[]}
 manual=automatic=None;last_beat=0
 def beat(force=False):
  nonlocal last_beat
  if force or time.monotonic()-last_beat>=.3:
   if automatic:api('gimbal-follow/heartbeat',{'session':automatic})
   elif manual:api('gimbal/heartbeat',{'session':manual})
   last_beat=time.monotonic()
 def tracking():
  until=time.monotonic()+4
  while time.monotonic()<until:
   beat();v=api('vision/status')
   if v.get('valid') and v.get('state')=='TRACKING':return v
   time.sleep(.06)
  raise RuntimeError('真实色块尚未稳定锁定')
 def center():
  api('gimbal/set',{'session':manual,'yaw':args.initial_yaw,'pitch':args.initial_pitch})
  def pulse(n,axis):return profile[axis+'_center']+round(n*(profile[axis+'_center']-profile[axis+'_min'] if n<0 else profile[axis+'_max']-profile[axis+'_center'])/100.)
  expected_yaw=pulse(args.initial_yaw,'yaw');expected_pitch=pulse(args.initial_pitch,'pitch')
  until=time.monotonic()+2
  while time.monotonic()<until:
   beat();s=api('status');g=s.get('gimbal') or {}
   if abs(g.get('yaw_us',0)-expected_yaw)<=2 and abs(g.get('pitch_us',0)-expected_pitch)<=2:return
   time.sleep(.05)
  raise RuntimeError('真实云台尚未停稳在已保存中位')
 def mean_error(axis):
  vals=[];seq=None;target=None;until=time.monotonic()+1.5
  while len(vals)<4 and time.monotonic()<until:
   beat();v=api('vision/status')
   if v.get('valid') and v.get('state')=='TRACKING' and v['frame_seq']!=seq:
    if target is not None and target!=v['track_id']:raise RuntimeError('核对方向期间目标发生替换')
    target=v['track_id'];seq=v['frame_seq'];vals.append(v['error_'+axis])
   time.sleep(.04)
  if len(vals)<4:raise RuntimeError('核对方向所需真实相机帧不足')
  return statistics.median(vals),target
 try:
  info=api('ui/info');state=api('status');profile=api('gimbal/settings')
  assert info['source_version']=='0.29.0' and state['connected'],'等待0.29.0小手机主控记录连接'
  assert not state['control']['active'] and not state['drive']['active'],'请先停止已有云台/车辆会话'
  report['imu_before']=state.get('mpu',{});report['profile']=profile
  if not args.execute:report['result']='PREFLIGHT_ONLY';print(json.dumps({'preflight':'PASS','execute':False}));return
  c=api('camera/status')
  if not c['running']:api('camera/start',{'resolution':'640x480','fps':30})
  api('vision/config',{'mode':args.color,'enabled':True});tracking()
  manual=api('gimbal/start',{})['session'];center();tracking()
  signs={'yaw':-1,'pitch':1} if args.skip_probes else {}
  if args.skip_probes:report['axis_signs_reused_from_verified_probes']=signs.copy()
  for axis,key in ([] if args.skip_probes else [('yaw','x'),('pitch','y')]):
   center();tracking();before,target=mean_error(key)
   api('gimbal/set',{'session':manual,'yaw':args.initial_yaw+(args.probe_step if axis=='yaw' else 0),'pitch':args.initial_pitch+(args.probe_step if axis=='pitch' else 0)})
   time.sleep(.3);after,other=mean_error(key);delta=after-before
   report['axis_probes'].append({'axis':axis,'command_percent':args.probe_step,'before':before,'after':after,'delta':delta,'before_track':target,'after_track':other,'assumption':'target stationary during probe'})
   if other!=target or abs(delta)<.012:raise RuntimeError('微量试移不能确认'+axis+'方向；请保持物体静止且清晰')
   signs[axis]=1 if delta*args.probe_step<0 else -1
   report['axis_probes'][-1]['sign']=signs[axis]
  center();tracking();beat(True)
  if args.probe_only:report['result']='P7_AXIS_PROBES_LOGGED';return
  result=api('gimbal-follow/start',{'manual_session':manual,'confirmed':True,'yaw_sign':signs['yaw'],'pitch_sign':signs['pitch'],'both_axes':True})
  automatic=result['session'];manual=None
  print(json.dumps({'event':'AUTO_TRACKING_STARTED','axes':signs,'phone_imu_valid':state.get('mpu',{}).get('valid',False)}),flush=True)
  until=time.monotonic()+max(3,min(30,args.seconds));last_status=0;status=None
  while time.monotonic()<until:
   beat();v=api('vision/status');f=api('gimbal-follow/status')
   if time.monotonic()-last_status>=.5:status=api('status');last_status=time.monotonic()
   report['samples'].append({'at':time.monotonic(),'frame':v.get('frame_seq'),'age_ms':v.get('source_age_ms'),'target':v.get('track_id'),'x':v.get('error_x'),'y':v.get('error_y'),'tracking':f['active'],'follow_state':f.get('state'),'gimbal':status.get('gimbal'),'imu_valid':status.get('mpu',{}).get('valid')})
   if not f['active']:
    report['end_reason']=f.get('message');break
   time.sleep(.04)
  report['result']='PHYSICAL_P7_OUTPUT_LOGGED_MECHANICAL_CONFIRMATION_PENDING'
 except Exception as e:
  report['result']='INCOMPLETE';report['error']=str(e);print(json.dumps({'result':'INCOMPLETE','error':str(e)},ensure_ascii=False),flush=True)
 finally:
  try:
   if automatic:report['stop']=api('gimbal-follow/stop',{'session':automatic})
   elif manual:
    report['stop']=api('gimbal/stop',{'session':manual})
  except Exception as e:report['stop_unconfirmed']=str(e)
  (out/'phone-follow-physical.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'result':report.get('result'),'samples':len(report['samples']),'stop_confirmed':report.get('stop',{}).get('stop_confirmed',report.get('stop',{}).get('stopped',False))},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
