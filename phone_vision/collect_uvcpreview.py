"""Read only this project's development app files after phone reconnects to PC."""
from pathlib import Path
import subprocess,json,datetime,re
root=Path(__file__).resolve().parents[2]
adb=root/'tmp/android-tools/platform-tools/adb.exe'
out=root/'output/usb_camera_check'/('phone-'+datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y%m%d-%H%M%S'))
out.mkdir(exist_ok=True)
def call(*args):
    p=subprocess.run([str(adb),*args],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=20)
    if p.returncode:raise RuntimeError(p.stderr.decode('utf-8',errors='replace'))
    return p.stdout
states=[r.split()[1] for r in call('devices').decode().splitlines()[1:] if r.strip()]
assert states==['device'],'One authorized phone required'
files=call('shell','run-as','cn.zhixing.uvcpreview','ls','files').decode().splitlines()
names=[n for n in files if re.fullmatch(r'uvc-\d+\.jsonl',n)]
names=sorted(names)[-5:]+[n for n in ['external-camera.jpg','latest-uvc-status.json'] if n in files]
events=[];sessions=[]
for n in names:
    content=call('exec-out','run-as','cn.zhixing.uvcpreview','cat','files/'+n)
    assert len(content)<=2*1024*1024
    (out/n).write_bytes(content)
    if n.endswith('.jsonl'):
        current=[json.loads(line) for line in content.decode('utf-8').splitlines()]
        events.extend(current)
        sessions.append({'file':n,'max_received_frames':max((e.get('frames',0) for e in current),default=0),
                         'preview_started':[e for e in current if e['event']=='preview_started'],
                         'errors':[e for e in current if 'error' in e['event']],
                         'frame_stats':[e for e in current if e['event']=='frame_stats'][-5:],
                         'snapshot_saved':any(e['event']=='snapshot_saved' for e in current)})
summary={'files':names,'max_received_frames':max((e.get('frames',0) for e in events),default=0),
         'preview_started':[e for e in events if e['event']=='preview_started'],
         'errors':[e for e in events if 'error' in e['event']],
         'frame_stats': [e for e in events if e['event']=='frame_stats'][-5:],
         'snapshot_saved':any(e['event']=='snapshot_saved' for e in events),'motor_commands':'NONE'}
summary['sessions']=sessions
summary['latest_session']=sessions[-1] if sessions else None
(out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False));print('Evidence:',out)
