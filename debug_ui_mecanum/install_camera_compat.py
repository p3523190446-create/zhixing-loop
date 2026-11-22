"""Update the already configured K99; preserve app data and verify APK readback."""
from pathlib import Path
import argparse,datetime,hashlib,json,re,subprocess,sys

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/onboard_dashboard/camera-compat-20261026'
ADB=ROOT/'tmp/android-tools/platform-tools/adb.exe'
PACKAGE='cn.zhixing.dashboard'
EXPECTED='d7e6c5a1f27cb66331c48fcd0e7527b223b4e9366fe0c771cd7b6086e933a6c0'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(*args,timeout=20,check=True):return subprocess.run([str(ADB),*args],capture_output=True,timeout=timeout,check=check)
def main():
    global OUT,EXPECTED
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=OUT);args=parser.parse_args();OUT=args.out
    build=json.loads((OUT/'build-result.json').read_text(encoding='utf-8'))
    if build['package']!=PACKAGE or build.get('signature')!='VERIFIED':raise RuntimeError('Expected verified dashboard build report')
    EXPECTED=build['sha256'];version=build['version'];target_code=int(build.get('version_code',version.split('.')[-1]))
    apk=OUT/'zhixing-dashboard.apk'
    if digest(apk)!=EXPECTED:raise RuntimeError('APK changed; verify the new build before updating')
    rows=run('devices').stdout.decode().splitlines()[1:]
    devices=[r.split()[0] for r in rows if len(r.split())==2 and r.split()[1]=='device']
    if not devices:
        report=dict(deployment='NOT_INSTALLED',reason='ADB_DEVICE_ABSENT',apk_sha256=EXPECTED,camera_acceptance='NOT_RUN')
        (OUT/'installation-status.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report));return 2
    if len(devices)!=1:raise RuntimeError('Multiple ADB devices; refuse ambiguous update')
    serial=devices[0]
    def adb(*a,**kw):return run('-s',serial,*a,**kw)
    platform=adb('shell','getprop','ro.board.platform').stdout.decode().strip()
    sdk=adb('shell','getprop','ro.build.version.sdk').stdout.decode().strip()
    if platform!='mt6739' or sdk!='28':raise RuntimeError('Connected phone differs from the verified K99 platform')
    def package_path(name):
        text=adb('shell','pm','path',name).stdout.decode().strip()
        if not re.fullmatch(r'package:/data/app/[A-Za-z0-9._=+/-]+/base\.apk',text):raise RuntimeError('Expected existing package path not found')
        return text[8:]
    package_path('cn.zhixing.localbench') # Prior task's app must already be present.
    old_path=package_path(PACKAGE)
    info=adb('shell','dumpsys','package',PACKAGE).stdout.decode(errors='replace')
    code=re.search(r'versionCode=(\d+)',info)
    if not code or int(code.group(1))>target_code:raise RuntimeError('Refuse unknown or newer dashboard version')
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    before=OUT/('installed-before-'+stamp+'.apk')
    adb('pull',old_path,str(before),timeout=40)
    pref=adb('shell','run-as',PACKAGE,'cat','shared_prefs/web.xml',check=False)
    pref_hash=hashlib.sha256(pref.stdout).hexdigest() if pref.returncode==0 else None
    if digest(before)!=EXPECTED:
        result=adb('install','-r',str(apk),timeout=60)
        if 'Success' not in result.stdout.decode(errors='replace'):raise RuntimeError('Installer did not confirm success')
    after=OUT/('installed-readback-'+stamp+'.apk')
    adb('pull',package_path(PACKAGE),str(after),timeout=40)
    if digest(after)!=EXPECTED:raise RuntimeError('Installed APK readback differs')
    if pref_hash:
        now=adb('shell','run-as',PACKAGE,'cat','shared_prefs/web.xml')
        if hashlib.sha256(now.stdout).hexdigest()!=pref_hash:raise RuntimeError('Web configuration changed; inspect preserved files before continuing')
    report=dict(deployment='INSTALLED_READBACK_VERIFIED',version=version,apk_sha256=EXPECTED,
        previous_apk=str(before),configuration_hash_preserved=bool(pref_hash),app_launched=False,
        app_data_cleared=False,controller_commands_sent=False,camera_acceptance='NOT_RUN')
    (OUT/'installation-status.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False));return 0
if __name__=='__main__':sys.exit(main())
