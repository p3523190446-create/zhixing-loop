"""Install a new permission-free benchmark app; preserve all existing car apps."""
import bootstrap
from pathlib import Path
import argparse,hashlib,json,subprocess,time

ROOT=bootstrap.ROOT;OUT=ROOT/'output/onboard_dashboard/phone-first-20261025'
ADB=ROOT/'tmp/android-tools/platform-tools/adb.exe'

def run(*args,timeout=30):return subprocess.run([str(ADB),*args],capture_output=True,check=True,timeout=timeout)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--collect-only',action='store_true');args=parser.parse_args()
    if run('get-state').stdout.decode().strip()!='device':raise RuntimeError('ADB phone is not ready')
    probe=subprocess.run([str(ADB),'shell','pm','path','cn.zhixing.localbench'],capture_output=True,timeout=10)
    if probe.returncode not in (0,1) or probe.stderr.strip():raise RuntimeError('Could not check existing package')
    existing=probe.stdout.decode().strip()
    if existing and not args.collect_only:raise RuntimeError('Benchmark package already exists; no update or data clearing performed')
    if args.collect_only and not existing:raise RuntimeError('Benchmark package is not installed')
    apk=OUT/'zhixing-phone-local-bench-0.1.apk'
    wait_timeout=args.collect_only
    if not args.collect_only:
        install=run('install',str(apk),timeout=60).stdout.decode()
        if 'Success' not in install:raise RuntimeError('Installer did not confirm success')
        try:
            launch=run('shell','am','start','-W','-n','cn.zhixing.localbench/.MainActivity','--ez','auto_run','true').stdout.decode()
            (OUT/'app-launch.log').write_text(launch,encoding='utf-8')
        except subprocess.TimeoutExpired:
            wait_timeout=True
    result=None
    for _ in range(90):
        proc=subprocess.run([str(ADB),'shell','run-as','cn.zhixing.localbench','cat','files/result.json'],capture_output=True,timeout=5)
        if proc.returncode==0:
            try:result=json.loads(proc.stdout.decode());break
            except ValueError:pass
        time.sleep(1)
    if result is None:raise RuntimeError('App benchmark did not complete; application and logs preserved')
    assert result['mode']=='ANDROID_OFFLINE_ALGORITHM_ONLY' and not result['actuator_access']
    (OUT/'app-local-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    installed=run('shell','pm','path','cn.zhixing.localbench').stdout.decode().strip().removeprefix('package:')
    run('pull',installed,str(OUT/'installed-local-bench.apk'),timeout=40)
    digest=hashlib.sha256((OUT/'installed-local-bench.apk').read_bytes()).hexdigest()
    assert digest==hashlib.sha256(apk.read_bytes()).hexdigest()
    report=dict(package='cn.zhixing.localbench',version='0.1',installed_sha256=digest,
        readback_matches=True,local_app_test_passed=True,camera_opened=False,controller_access=False,
        old_dashboard_modified=False,existing_apps_uninstalled=False,physical_usb_unplug_test=False,
        initial_launch_wait_timed_out=wait_timeout,physical_ui_verified=False)
    (OUT/'app-install-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'installation':report,'result':result}))

if __name__=='__main__':main()
