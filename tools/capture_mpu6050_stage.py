"""Pause the verified idle PC serial owner for read-only MPU capture, then restore it."""
from pathlib import Path
import argparse,datetime,json,os,subprocess,sys,time,urllib.request
ROOT=Path(__file__).resolve().parents[2]
TOOLS=Path(__file__).resolve().parent
BASE=ROOT/'output/onboard_dashboard/mpu6050-20261025'
def main():
    p=argparse.ArgumentParser();p.add_argument('--service-pid',type=int,required=True)
    p.add_argument('--stage',choices=['flat','front-raised','left-raised'],required=True)
    p.add_argument('--seconds',type=float,default=6);p.add_argument('--holdout',type=float,default=0)
    a=p.parse_args();assert 1<=a.seconds<=30 and (a.holdout==0 or 1<=a.holdout<=15)
    stamp=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y%m%d-%H%M%S')
    out=BASE/(a.stage+'-'+stamp);out.mkdir(parents=True,exist_ok=False)
    meta=json.loads((ROOT/'output/onboard_dashboard/line-ui-20261025/deployment-status.json').read_text(encoding='utf-8'))
    url=meta['pc']['url'].rsplit('/desktop',1)[0];status_url=url+'/api/status';base=url.split(':8795',1)[1]
    status=json.load(urllib.request.urlopen(status_url,timeout=4))
    assert status['connected'] and status['age_ms']<3000
    assert not status['drive']['active'] and not status['drive']['moving']
    assert not status['gimbal']['active'] and not status['recording']['active'] and not status['recording'].get('finishing')
    record=dict(stage=a.stage,user_report='Requested physical placement completed by reply1',
        writes='NONE; no firmware/reset/calibration/compatibility/motion command',before=status)
    stopped=False;env={**os.environ,'PYTHONIOENCODING':'utf-8'}
    def capture(name,seconds):
        with (out/(name+'.log')).open('w',encoding='utf-8') as log:
            proc=subprocess.run([sys.executable,str(TOOLS/'collect_mpu6050.py'),'--port','COM5','--seconds',str(seconds),
                '--out',str(out/(name+'.json'))],stdout=log,stderr=subprocess.STDOUT,env=env,timeout=50)
        if proc.returncode:raise RuntimeError(name+' capture failed; original replies preserved')
        d=json.loads((out/(name+'.json')).read_text(encoding='utf-8'))
        assert d['samples'] and all(x['mpu']['valid'] for x in d['samples']), 'MPU is not currently sampling; no reference accepted'
        for x in d['samples']:
            values=list(map(int,x['MPU_STATUS'].split(',')[1:]))
            assert values[3:5]==[0x69,0x72], 'Identity/address changed; do not reuse prior trial'
    try:
        command=(f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={a.service_pid}';"
            "if(!$p -or $p.CommandLine -notlike '*debug_ui*speed_server.py*--port 8795*'){throw 'Service identity changed'};"
            f"Stop-Process -Id {a.service_pid} -ErrorAction Stop")
        subprocess.run(['powershell','-NoProfile','-Command',command],check=True,capture_output=True,timeout=15)
        stopped=True;time.sleep(.3);capture('samples',a.seconds)
        if a.holdout:capture('holdout',a.holdout)
        record['capture']='PASS'
    except Exception as e:record['error']=str(e)
    finally:
        if stopped:
            log=(out/'restored-server.log').open('a',encoding='utf-8')
            proc=subprocess.Popen([sys.executable,str(ROOT/'知行回路软件/debug_ui/speed_server.py'),
                '--bind','0.0.0.0','--port','8795','--base',base],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                env=env,creationflags=subprocess.CREATE_NO_WINDOW)
            log.close();record['service_pid_after']=proc.pid
            for _ in range(40):
                try:
                    current=json.load(urllib.request.urlopen(status_url,timeout=1))
                    if current.get('connected'):record['after']=current;record['service_restored']=True;break
                except Exception:pass
                time.sleep(.4)
        (out/'capture-run.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),capture=record.get('capture'),service_restored=record.get('service_restored'),
        service_pid_after=record.get('service_pid_after'),error=record.get('error')),ensure_ascii=False,indent=2))
    if record.get('error') or not record.get('service_restored'):raise SystemExit(1)
if __name__=='__main__':main()
