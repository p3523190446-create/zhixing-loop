"""Start/stop only the local algorithm viewer; optionally start the external camera.

The camera helper has exactly two fixed camera endpoints, no actuator endpoints.
Existing P9 service ownership and firmware remain untouched.
"""
import bootstrap
from pathlib import Path
import argparse, json, os, subprocess, sys, time, urllib.request
from server import OUT, HERE, Source

def camera(action):
    if action not in ('start','stop'):raise ValueError('Invalid camera action')
    source=Source()
    body=dict(resolution='640x480',fps=10) if action=='start' else {}
    request=urllib.request.Request(source.url+'/api/camera/'+action,
        data=json.dumps(body).encode('utf-8'),
        headers={'Origin':'http://127.0.0.1:8795','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(error.read().decode('utf-8')) from None

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['start','stop','status','camera-start','camera-stop'])
    p.add_argument('--record-seconds',type=int,default=60)
    cameras=p.add_mutually_exclusive_group()
    cameras.add_argument('--borrowed-camera',action='store_true')
    cameras.add_argument('--original-camera',action='store_true')
    a=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if a.action.startswith('camera-'):
        print(json.dumps(camera(a.action.split('-')[1])));return
    if a.action=='stop':
        import psutil
        runtime=json.loads((OUT/'runtime.json').read_text(encoding='utf-8'))
        proc=psutil.Process(runtime['pid'])
        command=proc.cmdline()
        if str(HERE/'server.py') not in command:
            raise RuntimeError('PID identity changed; process was not stopped')
        # Stop only this viewer's verified FFmpeg child when it owns USB031.
        for child in proc.children(recursive=True):
            try:
                args=child.cmdline()
                identity='vid_145f&pid_02ec' if runtime.get('camera_kind')=='original' else 'vid_04b4&pid_00c3'
                if child.name().lower()=='ffmpeg.exe' and any(identity in x.lower() for x in args):
                    child.terminate();child.wait(timeout=5)
            except psutil.NoSuchProcess:pass
        proc.terminate();proc.wait(timeout=6)
        print(json.dumps({'stopped':True,'camera':'unchanged'}));return
    if a.action=='status':
        with urllib.request.urlopen('http://127.0.0.1:8796/api/status',timeout=3) as response:
            print(response.read().decode('utf-8'));return
    try:
        with urllib.request.urlopen('http://127.0.0.1:8796/api/status',timeout=2) as response:
            d=json.load(response)
        if d.get('actuation_enabled') is False:
            requested='original' if a.original_camera else 'borrowed' if a.borrowed_camera else None
            current=(d.get('camera_source') or {}).get('camera_kind')
            if requested and current!=requested:
                raise RuntimeError('Existing viewer uses another camera; stop the verified viewer before changing input')
            if requested and not (d.get('camera_source') or {}).get('valid'):
                raise RuntimeError('Existing viewer has no fresh camera frames: '+str((d.get('camera_source') or {}).get('error')))
            print(json.dumps({'already_running':True,'url':'http://127.0.0.1:8796/'}));return
        raise RuntimeError('Port already belongs to a different service')
    except urllib.error.URLError:pass
    log=(OUT/'server.log').open('a',encoding='utf-8')
    command=[sys.executable,str(HERE/'server.py'),'--record-seconds',str(a.record_seconds)]
    if a.borrowed_camera:command.append('--borrowed-camera')
    if a.original_camera:command.append('--original-camera')
    proc=subprocess.Popen(command,
        cwd=HERE,stdout=log,stderr=subprocess.STDOUT,
        env={**os.environ,'PYTHONIOENCODING':'utf-8'},creationflags=subprocess.CREATE_NO_WINDOW)
    log.close()
    for _ in range(60):
        if proc.poll() is not None:raise RuntimeError('Server stopped; see server.log')
        try:
            with urllib.request.urlopen('http://127.0.0.1:8796/api/status',timeout=1) as response:
                state=json.load(response)
                if response.status==200:
                    if a.original_camera or a.borrowed_camera:
                        camera=state.get('camera_source') or {}
                        if camera.get('error'):raise RuntimeError('Camera did not start: '+camera['error'])
                        if not camera.get('valid'):
                            time.sleep(.25);continue
                    break
        except urllib.error.URLError:time.sleep(.3)
    else:raise RuntimeError('Server startup timeout')
    print(json.dumps({'started':True,'pid':proc.pid,'url':'http://127.0.0.1:8796/'}))

if __name__=='__main__':main()
