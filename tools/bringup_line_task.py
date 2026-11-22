"""Temporarily release the idle P9 owner, deploy and read only, restore its URL."""
from pathlib import Path
import datetime,json,os,subprocess,sys,time,urllib.request
ROOT=Path(__file__).resolve().parents[2];TOOLS=Path(__file__).resolve().parent
OUT=ROOT/'output/onboard_dashboard/phone-line-control-20261026'
def main():
 runtime=json.loads((ROOT/'output/onboard_dashboard/pc-speed-20261021/runtime.json').read_text(encoding='utf-8'))
 url=runtime['dashboard_url'].rsplit('/desktop',1)[0];status_url=url+'/api/status';base=runtime['base'];pid=int(runtime['pid'])
 before=json.load(urllib.request.urlopen(status_url,timeout=4))
 assert before['connected'] and before['age_ms']<3000 and not before['drive']['active'] and not before['drive']['moving'] and not before['gimbal']['active']
 assert not before['recording']['active'] and not before['recording'].get('finishing')
 record={'started_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'before':before,'service_pid_before':pid,'nonzero_actuator_requests':0,'compatibility_enable_commands':0}
 env={**os.environ,'PYTHONIOENCODING':'utf-8'};stopped=False
 try:
  command=f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={pid}';if(!$p -or $p.CommandLine -notlike '*debug_ui*speed_server.py*--port 8795*'){{throw 'Service identity changed'}};Stop-Process -Id {pid} -ErrorAction Stop"
  subprocess.run(['powershell','-NoProfile','-Command',command],check=True,capture_output=True,timeout=15);stopped=True
  with (OUT/'flash.log').open('w',encoding='utf-8') as log:
   p=subprocess.run([sys.executable,str(TOOLS/'flash_r1_line_task.py'),'--execute'],stdout=log,stderr=subprocess.STDOUT,env=env,timeout=150)
  record['flash_returncode']=p.returncode
  if p.returncode:raise RuntimeError('Flash failed; inspect full backup and rollback record')
  sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'));import serial
  link=serial.Serial();link.port='COM5';link.baudrate=115200;link.timeout=.1;link.write_timeout=1;link.dtr=False;link.rts=False;link.open()
  def query(command,prefix=None):
   link.write((command+'\n').encode('ascii'));link.flush();until=time.monotonic()+2
   while time.monotonic()<until:
    line=link.readline().decode('ascii',errors='replace').strip()
    if line.startswith(prefix or command+','):return line
    if line.startswith('ERR'):raise RuntimeError(line)
   raise TimeoutError(command)
  def nums(c,p=None):return list(map(int,query(c,p).split(',')[1:]))
  with link:
   link.reset_input_buffer();record['caps']=query('LINE_TASK_CAPS');assert record['caps']=='LINE_TASK_CAPS,1,50,100,0'
   record['samples']=[];until=time.monotonic()+30
   while time.monotonic()<until:
    sample={c:nums(c,p) for c,p in [('LINE_TASK_STATUS',None),('LINE_STATUS',None),('MPU_STATUS',None),('DRIVE_STATUS','DRIVE,'),('GIMBAL_STATUS','GIMBAL,')]}
    assert sample['LINE_TASK_STATUS'][1:6]==[0,0,0,0,0]
    assert sample['DRIVE_STATUS'][1:3]==[0,0] and sample['DRIVE_STATUS'][5:7]==[0,0] and sample['GIMBAL_STATUS'][2]==0
    record['samples'].append(sample)
    if len(record['samples'])>=5 and sample['LINE_STATUS'][10:12]==[1,1] and sample['LINE_STATUS'][2]>record['samples'][-2]['LINE_STATUS'][2]:break
    time.sleep(.5)
   assert record['samples'][-1]['LINE_STATUS'][10:12]==[1,1],'Line source never became fresh'
 except Exception as error:record['error']=str(error)
 finally:
  if stopped:
   log=(OUT/'restored-p9-service.log').open('a',encoding='utf-8')
   service=subprocess.Popen([sys.executable,str(ROOT/'知行回路软件/debug_ui/speed_server.py'),'--bind',runtime.get('bind','0.0.0.0'),'--port','8795','--base',base],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,env=env,creationflags=subprocess.CREATE_NO_WINDOW);log.close();record['service_pid_after']=service.pid
   for _ in range(40):
    try:
     state=json.load(urllib.request.urlopen(status_url,timeout=1))
     if state.get('connected'):record['after']=state;record['service_restored']=True;break
    except Exception:pass
    time.sleep(.5)
  (OUT/'board-deployment.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in record.items() if k not in ('before','after','samples')},ensure_ascii=False))
 if record.get('error') or not record.get('service_restored'):raise SystemExit(1)
if __name__=='__main__':main()
