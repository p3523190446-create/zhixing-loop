"""Execute isolated production-controller checks in the connected Android runtime."""
from pathlib import Path
import datetime,json,subprocess,os
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OUT=Path(os.environ.get('ZX_GIMBAL_CHECK_OUT',str(ROOT/'output/onboard_dashboard/gimbal-follow-20261107')));OUT.mkdir(parents=True,exist_ok=True)
ADB=ROOT/'tmp/android-tools/platform-tools/adb.exe';CACHE=Path.home()/'.cache/zhixing-android-tools'
JDK=Path(r'C:\Program Files\BellSoft\LibericaJDK-17')/'bin'
stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
work=Path.home()/'.cache'/('gimbal-follow-check-'+stamp);classes=work/'classes';classes.mkdir(parents=True);dex=work/'dex';dex.mkdir()
def run(*args):
 r=subprocess.run([str(a) for a in args],capture_output=True,timeout=90)
 if r.returncode:raise RuntimeError(r.stdout.decode('utf-8','replace')+r.stderr.decode('utf-8','replace'))
 return r.stdout
devices=[row.split()[0] for row in run(ADB,'devices').decode().splitlines()[1:] if len(row.split())==2 and row.split()[1]=='device']
if len(devices)!=1:raise RuntimeError('Expected one connected phone')
serial=devices[0]
if run(ADB,'-s',serial,'shell','getprop','ro.board.platform').decode().strip()!='mt6739':raise RuntimeError('Expected K99')
android=next(CACHE.glob('platform-33-ext3_r03/**/android.jar'));d8=next(CACHE.glob('build-tools_r35_windows/**/lib/d8.jar'))
sources=['android/ControlBroker.java','android/GimbalSettings.java','android/GimbalFollower.java','checks/GimbalCalibrationChecks.java','checks/GimbalFollowChecks.java']
run(JDK/'javac.exe','-encoding','UTF-8','--release','8','-cp',android,'-d',classes,*[HERE/s for s in sources])
jar=work/'checks.jar';run(JDK/'jar.exe','cf',jar,'-C',classes,'.')
run(JDK/'java.exe','-cp',d8,'com.android.tools.r8.D8','--min-api','26','--lib',android,'--output',dex,jar)
remote='/data/local/tmp/zhixing_follow_checks_'+stamp
run(ADB,'-s',serial,'shell','mkdir',remote);run(ADB,'-s',serial,'push',dex/'classes.dex',remote+'/classes.dex')
reports={}
for name in ['GimbalCalibrationChecks','GimbalFollowChecks']:
 raw=run(ADB,'-s',serial,'shell','CLASSPATH='+remote+'/classes.dex app_process /system/bin cn.zhixing.dashboard.'+name).decode('utf-8','replace')
 (OUT/(name+'.log')).write_text(raw,encoding='utf-8');reports[name]=json.loads(raw.strip().splitlines()[-1])
(OUT/'software-checks.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
print(json.dumps(reports))
