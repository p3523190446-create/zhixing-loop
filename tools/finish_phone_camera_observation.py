"""Read back a bounded passive phone capture and measure phone JPEG publication."""
import argparse
import json
from pathlib import Path
import re
import shlex
import statistics
import io
import subprocess

ROOT=Path(__file__).resolve().parents[2]
ADB=ROOT/'tmp/android-tools/platform-tools/adb.exe'
SERIAL='0123456789ABCDEF'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('manifest',type=Path)
args=parser.parse_args()
manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
remote=manifest['remote_directory']
if not re.fullmatch(r'/data/local/tmp/zhixing_phone_camera_\d{8}_\d{6}',remote):
    raise SystemExit('Unexpected recorder directory')

def adb(*a,check=True):
    return subprocess.run([str(ADB),'-s',SERIAL,*a],capture_output=True,timeout=25,check=check)

def shell(command):
    return adb('shell',command,check=False).stdout.decode('utf-8','replace').strip()

if shell('getprop ro.board.platform')!='mt6739' or shell('getprop ro.build.version.sdk')!='28':
    raise SystemExit('Configured phone not connected')
pid=str(manifest['pid'])
if not pid.isdigit():raise SystemExit('Unexpected process ID')
command=shell('cat /proc/'+pid+'/cmdline').replace('\x00',' ')
if remote+'/observe-camera.sh' in command:
    shell('kill '+pid)
out=args.manifest.parent
readback=out/'readback';readback.mkdir(exist_ok=True)
adb('pull',remote+'/.',str(readback))

def response(path):
    if not path.exists():return None
    data=path.read_bytes();header,separator,body=data.partition(b'\r\n\r\n')
    if not separator or not header.startswith(b'HTTP/1.0 200 '):return None
    try:return json.loads(body.decode('utf-8'))
    except (UnicodeError,ValueError):return None

rows=[];invalid_responses=[]
for path in sorted(readback.glob('camera-*.http'),key=lambda p:int(p.stem.split('-')[1])):
    index=int(path.stem.split('-')[1]);camera=response(path)
    try:uptime=float((readback/('uptime-'+str(index)+'.txt')).read_text().split()[0])
    except (OSError,ValueError,IndexError):continue
    if camera is None:
        invalid_responses.append(index);continue
    compatibility=response(readback/('usb-'+str(index)+'.http')) or {}
    state=response(readback/('state-'+str(index)+'.http')) or {}
    devices=compatibility.get('system_usb_devices',[])
    rows.append(dict(index=index,uptime=uptime,camera=camera,
        usb_identities=sorted(d.get('vid_pid','') for d in devices),
        telemetry_connected=state.get('connected'),
        control_active=(state.get('control') or {}).get('active'),
        drive_active=(state.get('drive') or {}).get('active')))
valid=[r for r in rows if r['camera'].get('valid') and r['camera'].get('running')
       and '145F:02EC' in r['camera'].get('source','')]
intervals=[]
for first,second in zip(rows,rows[1:]):
    a,b=first['camera'],second['camera']
    dt=second['uptime']-first['uptime']
    if (a.get('valid') and b.get('valid') and '145F:02EC' in a.get('source','')
            and b.get('source')==a.get('source') and dt>0 and b.get('seq',0)>a.get('seq',0)):
        intervals.append(dict(seconds=dt,jpeg_fps=(b['seq']-a['seq'])/dt,
            callback_fps=(b.get('callback_count',0)-a.get('callback_count',0))/dt))
duration=sum(r['seconds'] for r in intervals)
overall=sum(r['seconds']*r['jpeg_fps'] for r in intervals)/duration if duration else None
report=dict(app_version=manifest.get('app_version'),sample_count=len(rows),valid_original_camera_samples=len(valid),
    observed_valid_duration_s=duration,jpeg_publication_fps=overall,
    median_interval_fps=statistics.median(r['jpeg_fps'] for r in intervals) if intervals else None,
    preview_screen_fps_verified=False,model_inference_tested=False,p7_communication_tested=False,
    controller_commands_sent=False,local_loopback_sampler=True,computer_algorithm_service_stopped=True,
    usb_coexistence_observed=any('145F:02EC' in r['usb_identities'] and '1A86:FE0C' in r['usb_identities'] for r in valid),
    any_control_active=any(r['control_active'] is True or r['drive_active'] is True for r in rows),
    invalid_http_samples=invalid_responses,intervals=intervals,rows=rows,
    limitations='Measures actual Android UVC-to-JPEG publication, not exposure-to-display latency. USB presence is not P7 communication or motion acceptance. No model was added by this diagnostic tool.')
metrics=[]
web_events=adb('shell','run-as','cn.zhixing.dashboard','cat','files/web-events.jsonl',check=False).stdout.decode('utf-8','replace')
for line in web_events.splitlines():
    try:event=json.loads(line)
    except ValueError:continue
    detail=event.get('detail','')
    if event.get('elapsed_ms',0)<manifest.get('start_uptime_ms',0) or event.get('event')!='web_console' or 'ZXR_PREVIEW_METRICS ' not in detail:continue
    try:metric=json.loads(detail.split('ZXR_PREVIEW_METRICS ',1)[1])
    except ValueError:continue
    metrics.append(dict(metric,phone_elapsed_ms=event.get('elapsed_ms')))
report['webview_load_metrics']=metrics
report['webview_load_fps_median']=statistics.median(m['load_fps'] for m in metrics if m.get('load_fps',0)>0) if any(m.get('load_fps',0)>0 for m in metrics) else None
report['preview_screen_fps_verified']=False
report['webview_image_load_fps_observed']=bool(metrics)
photos=[]
for path in readback.glob('frame-*.http'):
    data=path.read_bytes();head,separator,body=data.partition(b'\r\n\r\n')
    if separator and head.startswith(b'HTTP/1.0 200 ') and body.startswith(b'\xff\xd8') and body.endswith(b'\xff\xd9'):
        target=out/(path.stem+'.jpg');target.write_bytes(body)
        from PIL import Image
        dimensions=Image.open(io.BytesIO(body)).size
        photos.append(dict(file=target.name,width=dimensions[0],height=dimensions[1]))
report['actual_phone_jpegs']=photos
vision=[r['camera'].get('local_vision') for r in valid if isinstance(r['camera'].get('local_vision'),dict)]
report['local_vision_states']=sorted(set(v.get('state','') for v in vision))
report['local_vision_processing_ms_median']=statistics.median(v['processing_ms'] for v in vision if 'processing_ms' in v) if any('processing_ms' in v for v in vision) else None
report['local_vision_valid_samples']=sum(bool(v.get('valid')) for v in vision)
report['target_offsets']=[dict(frame_seq=v.get('frame_seq'),x=v.get('error_x'),y=v.get('error_y'),state=v.get('state')) for v in vision if v.get('bbox')]
report['model_inference_tested']=False

(out/'phone-camera-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('rows','intervals','limitations','webview_load_metrics','target_offsets')},ensure_ascii=False))
