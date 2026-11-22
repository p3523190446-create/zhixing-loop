"""Passive bounded on-phone original-camera observation, surviving USB removal.

Reads existing app HTTP status on loopback only. Never starts camera or control.
"""
import datetime
import json
from pathlib import Path
import re
import shlex
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
ADB=ROOT/'tmp/android-tools/platform-tools/adb.exe'
SERIAL='0123456789ABCDEF'

def adb(*args,check=True):
    return subprocess.run([str(ADB),'-s',SERIAL,*args],capture_output=True,check=check,timeout=25)

def shell(command):
    return adb('shell',command).stdout.decode('utf-8','replace').strip()

if shell('getprop ro.board.platform')!='mt6739' or shell('getprop ro.build.version.sdk')!='28':
    raise SystemExit('Configured phone is not connected')
runtime=json.loads(shell('run-as cn.zhixing.dashboard cat files/web-runtime.json'))
port=runtime.get('port');base=runtime.get('base')
if not isinstance(port,int) or not 8780<=port<=8789 or not isinstance(base,str) or not re.fullmatch('/[A-Za-z0-9_-]{24,64}',base):
    raise SystemExit('Unexpected app runtime address')
stamp=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
out=ROOT/'output/onboard_dashboard/phone-original-20261026'/stamp
out.mkdir(parents=True,exist_ok=False)
forward=adb('forward','tcp:0','tcp:'+str(port)).stdout.decode().strip()
if not forward.isdigit():raise SystemExit('No temporary local forward')
try:
    readiness={}
    for path in ('ui/info','camera/status','camera/compatibility'):
        with urllib.request.urlopen('http://127.0.0.1:'+forward+base+'/api/'+path,timeout=5) as response:
            readiness[path]=json.load(response)
    (out/'readiness.json').write_text(json.dumps(readiness,ensure_ascii=False,indent=2),encoding='utf-8')
finally:
    adb('forward','--remove','tcp:'+forward)
start_uptime_ms=float(shell('cat /proc/uptime').split()[0])*1000
remote='/data/local/tmp/zhixing_phone_camera_'+stamp
request=lambda endpoint:'GET '+base+'/api/'+endpoint+' HTTP/1.0\r\nHost: 127.0.0.1:'+str(port)+'\r\nConnection: close\r\n\r\n'
script='''#!/system/bin/sh
cd REMOTE || exit 1
echo $$ > observer.pid
date > started.txt
deadline=$(($(date +%s)+300))
index=0
photos=0
while [ $(date +%s) -lt "$deadline" ]; do
  cat /proc/uptime > "uptime-$index.txt"
  printf %s CAMERA_STATUS | toybox nc -w 2 -W 2 127.0.0.1 PORT > "camera-$index.http" 2> "camera-$index.error"
  if [ $((index%8)) -eq 0 ]; then printf %s USB_STATUS | toybox nc -w 2 -W 2 127.0.0.1 PORT > "usb-$index.http" 2> "usb-$index.error"; fi
  if [ $((index%2)) -eq 0 ]; then printf %s STATE | toybox nc -w 2 -W 2 127.0.0.1 PORT > "state-$index.http" 2> "state-$index.error"; fi
  if [ "$photos" -lt 3 ] && [ $((index%8)) -eq 0 ] && grep -q '"phase":"STREAMING"' "camera-$index.http"; then
    printf %s CAMERA_FRAME | toybox nc -w 2 -W 2 127.0.0.1 PORT > "frame-$index.http" 2> "frame-$index.error"
    photos=$((photos+1))
  fi
  index=$((index+1))
  sleep 0.5
done
date > completed.txt
'''.replace('REMOTE',shlex.quote(remote)).replace('CAMERA_STATUS',shlex.quote(request('camera/status'))).replace('USB_STATUS',shlex.quote(request('camera/compatibility'))).replace('STATE',shlex.quote(request('status'))).replace('CAMERA_FRAME',shlex.quote(request('camera/frame'))).replace('PORT',str(port))
local=out/'observe-camera.sh'
local.write_text(script,encoding='utf-8',newline='\n')
shell('mkdir '+shlex.quote(remote))
adb('push',str(local),remote+'/observe-camera.sh')
pid=shell('nohup sh '+shlex.quote(remote+'/observe-camera.sh')+' > '+shlex.quote(remote+'/launch.txt')+' 2>&1 < /dev/null & echo $!')
if not pid.isdigit() or remote+'/observe-camera.sh' not in shell('cat /proc/'+pid+'/cmdline').replace('\x00',' '):
    raise SystemExit('Passive observer did not persist')
manifest=dict(remote_directory=remote,pid=int(pid),duration_limit_seconds=300,
    camera_started_by_tool=False,controller_commands_sent=False,wireless_debugging_enabled=False,
    start_uptime_ms=start_uptime_ms,sample_interval_seconds=0.5,app_version=readiness['ui/info'].get('source_version'),computer_compute_required=False)
(out/'observation.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(manifest=str(out/'observation.json'),**manifest,initial_camera=readiness['camera/status']),ensure_ascii=False))
