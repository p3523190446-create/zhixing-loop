"""Run production gimbal logic on Android with a fake, isolated controller."""
from pathlib import Path
import datetime,json,subprocess
HERE=Path(__file__).resolve().parent; ROOT=HERE.parent.parent
OUT=ROOT/'output/onboard_dashboard/gimbal-calibration-20261026';OUT.mkdir(exist_ok=True)
ADB=ROOT/'tmp/android-tools/platform-tools/adb.exe';CACHE=Path.home()/'.cache/zhixing-android-tools'
JDK=Path(r'C:\Program Files\BellSoft\LibericaJDK-17')/'bin'
stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f');work=Path.home()/'.cache'/('gimbal-check-'+stamp)
classes=work/'classes';classes.mkdir(parents=True);dex=work/'dex';dex.mkdir()
def run(*args):
 r=subprocess.run([str(a) for a in args],capture_output=True,timeout=90)
 if r.returncode:raise RuntimeError(r.stdout.decode('utf-8','replace')+r.stderr.decode('utf-8','replace'))
 return r.stdout
if run(ADB,'-s','0123456789ABCDEF','shell','getprop','ro.board.platform').decode().strip()!='mt6739':raise RuntimeError('K99 absent')
android=next(CACHE.glob('platform-33-ext3_r03/**/android.jar'));d8=next(CACHE.glob('build-tools_r35_windows/**/lib/d8.jar'))
run(JDK/'javac.exe','-encoding','UTF-8','--release','8','-cp',android,'-d',classes,HERE/'android/ControlBroker.java',HERE/'android/GimbalSettings.java',HERE/'checks/GimbalCalibrationChecks.java')
jar=work/'checks.jar';run(JDK/'jar.exe','cf',jar,'-C',classes,'.');run(JDK/'java.exe','-cp',d8,'com.android.tools.r8.D8','--min-api','26','--lib',android,'--output',dex,jar)
remote='/data/local/tmp/zhixing_gimbal_checks_'+stamp;run(ADB,'-s','0123456789ABCDEF','shell','mkdir',remote);run(ADB,'-s','0123456789ABCDEF','push',dex/'classes.dex',remote+'/classes.dex')
raw=run(ADB,'-s','0123456789ABCDEF','shell','CLASSPATH='+remote+'/classes.dex app_process /system/bin cn.zhixing.dashboard.GimbalCalibrationChecks')
report=json.loads(raw.decode().strip().splitlines()[-1]);(OUT/'broker-checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
