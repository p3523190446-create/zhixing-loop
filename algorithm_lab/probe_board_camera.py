"""Temporarily hand off an idle P9 owner for a bounded camera-only probe.

No flashing, reset, compatibility bypass, driver or gimbal command is issued.
The original HTTP service is restored with its original command line afterwards.
"""
import bootstrap
from pathlib import Path
import json, os, re, subprocess, time, urllib.request
import psutil, serial
from serial.tools import list_ports
from server import RUNTIME, OUT, Source, timestamp

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report=dict(at=timestamp(),mode='bounded_board_camera_probe',commands=[],motion_commands=False)
    source=Source()
    before=source.get('status')
    if (not before.get('connected') or before.get('link_age_ms',9999)>500
            or (before.get('drive') or {}).get('active')
            or (before.get('gimbal') or {}).get('active')
            or (before.get('control') or {}).get('active')
            or (before.get('recording') or {}).get('active')
            or any(before.get('speed_targets') or [0])
            or (before.get('camera') or {}).get('running')):
        raise RuntimeError('P9 service is not verified idle; it was not interrupted')
    runtime=json.loads(RUNTIME.read_text(encoding='utf-8'))
    proc=psutil.Process(runtime['pid']);command=proc.cmdline();cwd=proc.cwd()
    target=str(bootstrap.ROOT/'知行回路软件/debug_ui/speed_server.py')
    if target not in command or '--port' not in command or command[command.index('--port')+1]!='8795':
        raise RuntimeError('Original service process identity changed')
    report['before']=before
    ports=[p for p in list_ports.comports() if (p.vid,p.pid)==(0x1a86,0x8010)]
    if len(ports)!=1:raise RuntimeError('P9 identity is not unique')
    stopped=False
    try:
        proc.terminate();proc.wait(timeout=5);stopped=True
        time.sleep(.3)
        with serial.Serial(ports[0].device,115200,timeout=.05,write_timeout=.3) as link:
            link.reset_input_buffer();link.write(b'\n')
            def exchange(text,prefix,timeout=2):
                link.write((text+'\n').encode('ascii'));deadline=time.monotonic()+timeout
                while time.monotonic()<deadline:
                    answer=link.readline().decode('ascii',errors='replace').strip()
                    if answer.startswith(prefix):
                        report['commands'].append(dict(command=text,reply=answer));return answer
                raise TimeoutError('Camera reply timeout: '+text)
            caps=exchange('CAMERA_CAPS','CAMERA_')
            report['caps']=caps
            report['info_before']=exchange('CAMERA_INFO','CAMERA_')
            if caps!='CAMERA_CAPS,1,160,120':raise ValueError('Unsupported camera transport')
            started=exchange('CAMERA_START','CAMERA_',4)
            report['start_reply']=started
            if started=='CAMERA_STARTED':
                try:
                    deadline=time.monotonic()+5
                    while time.monotonic()<deadline:
                        text=exchange('CAMERA_INFO','CAMERA_')
                        values=list(map(int,text.split(',')[1:]))
                        if len(values)!=8:raise ValueError('Unexpected camera info')
                        if values[1]:break
                        time.sleep(.05)
                    else:raise TimeoutError('No fresh board camera frame')
                    ident,length=values[2:4]
                    if not 4<=length<=8192:raise ValueError('Frame length out of range')
                    data=bytearray()
                    for offset in range(0,length,64):
                        answer=exchange(f'CAMERA_CHUNK,{ident},{offset}','CAM')
                        match=re.fullmatch(r'CAMDATA,(\d+),(\d+),([0-9A-F]+)',answer)
                        if not match or (int(match[1]),int(match[2]))!=(ident,offset):
                            raise ValueError('Frame id/offset mismatch')
                        chunk=bytes.fromhex(match[3])
                        if len(chunk)!=min(64,length-offset):raise ValueError('Chunk length mismatch')
                        data.extend(chunk)
                    import cv2 as cv,numpy as np
                    image=cv.imdecode(np.frombuffer(data,np.uint8),cv.IMREAD_COLOR)
                    if image is None or image.shape[:2]!=(120,160):raise ValueError('Bad board JPEG')
                    (OUT/'board-camera-probe.jpg').write_bytes(data)
                    report.update(frame_bytes=len(data),frame_id=ident,frame_shape=[160,120],frame_verified=True)
                    exchange(f'CAMERA_RELEASE,{ident}','CAM')
                finally:
                    report['stop_reply']=exchange('CAMERA_STOP','CAMERA_')
            report['info_after']=exchange('CAMERA_INFO','CAMERA_')
    except Exception as error:report['error']=str(error)
    finally:
        if stopped:
            log=(OUT/'restored-p9-service.log').open('a',encoding='utf-8')
            restored=subprocess.Popen(command,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,
                env={**os.environ,'PYTHONIOENCODING':'utf-8'},creationflags=subprocess.CREATE_NO_WINDOW)
            log.close();report['restored_pid']=restored.pid
            for _ in range(30):
                try:
                    status=source.get('status')
                    if status.get('connected'):
                        report['after']=status;report['service_restored']=True;break
                except Exception:pass
                time.sleep(.3)
        (OUT/'board-camera-probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ['caps','start_reply','frame_verified','frame_bytes','error','service_restored','restored_pid']}))
    if not report.get('service_restored'):raise SystemExit(1)

if __name__=='__main__':main()
