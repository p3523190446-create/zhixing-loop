"""Deploy tested deltas under one P9 owner, preserving configuration. No nonzero TX."""
from pathlib import Path
import hashlib,json,os,signal,subprocess,sys,time,urllib.request,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];SW=ROOT/'知行回路软件';UI=SW/'debug_ui'
OUT=ROOT/'output/onboard_dashboard/mecanum-live-20261107';OUT.mkdir(parents=True,exist_ok=True)
PY=Path(sys.executable);ADB=ROOT/'tmp/android-tools/platform-tools/adb.exe'
RUNTIME=ROOT/'output/onboard_dashboard/pc-speed-20261021/runtime.json'
FLASHER=SW/'tools/flash_r1_mecanum_integrated.py'
PHONE_VERSION='0.26.1'
EXPECTED_FIRMWARE='R1_DRIVE_STARTUP_MANUAL_V8_20261023'
TARGET_FIRMWARE='R1_DRIVE_STARTUP_MANUAL_MECANUM_V2_20261107'
def adb(*args):return subprocess.run([str(ADB),*map(str,args)],capture_output=True,check=True,timeout=60).stdout
def main():
 assert '--execute' in sys.argv
 cfg=json.loads(RUNTIME.read_text(encoding='utf-8-sig'));base=cfg['base'];origin='http://127.0.0.1:8795'+base+'/api/'
 def api(path,body=None):
  req=urllib.request.Request(origin+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json','Origin':'http://127.0.0.1:8795'})
  with urllib.request.urlopen(req,timeout=5) as r:return json.load(r)
 state=api('status');assert state['connected'] and not state['drive']['active'] and not state['motor_active'], 'Existing controller is busy'
 assert state['firmware']==EXPECTED_FIRMWARE,'Unexpected live firmware baseline'
 assert all(x==0 for x in state['speed_targets']+state['speed_commands']+state['wheel_speeds'])
 (OUT/'before-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
 prefs={}
 for name in ('web.xml','gimbal_profile.xml','line_calibration.xml'):
  raw=adb('exec-out','run-as','cn.zhixing.dashboard','cat','shared_prefs/'+name);prefs[name]=raw
  folder=OUT/'private-phone-settings';folder.mkdir(exist_ok=True);(folder/name).write_bytes(raw)
 profile=None
 for node in ET.fromstring(prefs['line_calibration.xml']).findall('string'):
  try:
   value=json.loads(node.text)
   if isinstance(value,dict) and 'floor' in value and 'black' in value:profile=value
  except (ValueError,TypeError):pass
 assert profile is not None,'Cannot preserve verified calibration'
 api('drive/stop',{})
 # Only terminate the exact existing P9 owner recorded by its own runtime.
 command=subprocess.run(['powershell','-NoProfile','-Command',f'(Get-CimInstance Win32_Process -Filter "ProcessId={int(cfg["pid"])}").CommandLine'],capture_output=True,text=True,encoding='utf-8',errors='replace',check=True).stdout
 assert 'speed_server.py' in command and '8795' in command,command
 os.kill(int(cfg['pid']),signal.SIGTERM);time.sleep(.7)
 report={'nonzero_actuator_requests':0,'profile_id':profile['id'],'settings_preserved':False}
 try:
  subprocess.run([str(PY),'-X','utf8',str(FLASHER),'--execute'],check=True,timeout=180)
  sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
  import serial
  from serial.tools import list_ports
  ports=[p for p in list_ports.comports() if (p.vid,p.pid)==(0x1a86,0x8010)];assert len(ports)==1
  time.sleep(2)
  with serial.Serial(ports[0].device,115200,timeout=.02,write_timeout=.2) as link:
   def call(q,prefix):
    link.reset_input_buffer();link.write((q+'\n').encode());deadline=time.monotonic()+3;buf=b''
    while time.monotonic()<deadline:
     buf+=link.read(link.in_waiting or 1)
     while b'\n' in buf:
      line,buf=buf.split(b'\n',1);line=line.decode('ascii',errors='replace').strip()
      if line.startswith(prefix):return line
      if line.startswith('ERR'):raise RuntimeError(line)
    raise TimeoutError(q)
   call('LINE_TASK_STOP','LINE_TASK_STOPPED');call('DRIVE_STOP','DRIVE_STOPPED')
   report['identity']=call('DRIVE_ID','DRIVE_ID,');report['chassis']=call('DRIVE_CHASSIS','DRIVE_CHASSIS,')
   assert report['identity']=='DRIVE_ID,'+TARGET_FIRMWARE+',1'
   values=profile['floor']+profile['black'];assert len(values)==16
   assert call('LINE_TASK_CAL_SET,'+','.join(map(str,values)),'LINE_TASK_CAL_SAVED,')=='LINE_TASK_CAL_SAVED,'+str(profile['id'])
   assert call('LINE_TASK_CAL_GET','LINE_TASK_CAL,')=='LINE_TASK_CAL,'+str(profile['id'])+','+','.join(map(str,values))
   report['profile_restored_readback']=True;report['line_caps']=call('LINE_TASK_CAPS','LINE_TASK_CAPS,');report['line_loop']=call('LINE_TASK_LOOP','LINE_TASK_LOOP,')
  subprocess.run([str(PY),'-X','utf8',str(UI/'install_camera_compat.py'),'--out',str(OUT)],check=True,timeout=120)
  for name,raw in prefs.items():assert adb('exec-out','run-as','cn.zhixing.dashboard','cat','shared_prefs/'+name)==raw,name
  report['settings_preserved']=True;report['phone_version']=PHONE_VERSION
 finally:
  log=(OUT/'p9-restored-stdout.log').open('ab');err=(OUT/'p9-restored-stderr.log').open('ab')
  proc=subprocess.Popen([str(PY),str(UI/'speed_server.py'),'--bind','0.0.0.0','--port','8795','--base',base],cwd=UI,stdout=log,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
  log.close();err.close();report['p9_restored_pid']=proc.pid
  for _ in range(30):
   time.sleep(.4)
   try:
    final=api('status')
    if final.get('connected') and final.get('driver_profile',{}).get('ready')==1:
     report['p9_connected']=True;report['final_zero']=not final['drive']['active'] and all(x==0 for x in final['speed_targets']+final['speed_commands']);break
   except Exception:pass
  (OUT/'deployment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  print(json.dumps(report,ensure_ascii=False),flush=True)
 assert report.get('p9_connected') and report.get('final_zero')

if __name__=='__main__':main()
