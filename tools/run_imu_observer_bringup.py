"""Temporary PC telemetry maintenance, verified flash, static reads, restore same UI URL."""
from pathlib import Path
import argparse,datetime,json,os,subprocess,sys,time,urllib.request
ROOT=Path(__file__).resolve().parents[2]
TOOLS=Path(__file__).resolve().parent
OUT=ROOT/'output/onboard_dashboard/imu-observer-20261025'
def main():
    p=argparse.ArgumentParser();p.add_argument('--service-pid',type=int,required=True)
    p.add_argument('--restart-only',action='store_true');a=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    meta=json.loads((ROOT/'output/onboard_dashboard/line-ui-20261025/deployment-status.json').read_text(encoding='utf-8'))
    url=meta['pc']['url'];base=url.rsplit('/desktop',1)[0].split(':8795',1)[1]
    status_url=url.rsplit('/desktop',1)[0]+'/api/status'
    status=json.load(urllib.request.urlopen(status_url,timeout=4))
    assert status['connected'] and status['age_ms']<3000
    assert not status['drive']['active'] and not status['drive']['moving']
    assert not status['gimbal']['active'] and not status['recording']['active'] and not status['recording'].get('finishing')
    record=dict(started_at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        nonzero_motion_commands='NONE',service_pid_before=a.service_pid,before=status)
    stopped=False;env={**os.environ,'PYTHONIOENCODING':'utf-8'}
    def run(script,*args):
        with (OUT/(Path(script).stem+'.log')).open('w',encoding='utf-8') as log:
            q=subprocess.run([sys.executable,str(TOOLS/script),*map(str,args)],stdout=log,stderr=subprocess.STDOUT,env=env,timeout=150)
        return q.returncode
    try:
        # Verify the exact service before stopping; never kill another Python.
        command=(f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={a.service_pid}';"
            "if(!$p -or $p.CommandLine -notlike '*debug_ui*speed_server.py*--port 8795*'){throw 'Service identity changed'};"
            f"Stop-Process -Id {a.service_pid} -ErrorAction Stop")
        subprocess.run(['powershell','-NoProfile','-Command',command],check=True,capture_output=True,timeout=15)
        stopped=True;time.sleep(.5)
        if not a.restart_only:
            record['flash_returncode']=run('flash_r1_imu_observer.py','--execute')
            if record['flash_returncode']:raise RuntimeError('Flash failed; inspect flash verification and rollback')
            time.sleep(2)
            record['collector_returncode']=run('collect_imu_observer.py','--out',OUT/'static-live.json')
            if record['collector_returncode']:raise RuntimeError('Static collector failed; inspect raw record')
    except Exception as e:record['error']=str(e)
    finally:
        if stopped:
            log=(OUT/'restored-speed-server.log').open('a',encoding='utf-8')
            proc=subprocess.Popen([sys.executable,str(ROOT/'知行回路软件/debug_ui/speed_server.py'),
                '--bind','0.0.0.0','--port','8795','--base',base],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                env=env,creationflags=subprocess.CREATE_NO_WINDOW)
            log.close();record['service_pid_after']=proc.pid
            for _ in range(40):
                try:
                    current=json.load(urllib.request.urlopen(status_url,timeout=1))
                    if current.get('connected'):
                        record['after']=current;record['service_restored']=True;break
                except Exception:pass
                time.sleep(.5)
        (OUT/('restart-run.json' if a.restart_only else 'deployment-run.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if k not in ('before','after')},ensure_ascii=False,indent=2))
    if record.get('error') or not record.get('service_restored'):raise SystemExit(1)
if __name__=='__main__':main()
