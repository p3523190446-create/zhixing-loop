"""Run the production NV21 tracker, cadence and JSON view against Android fixtures."""
from pathlib import Path
import datetime,json,subprocess

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent
OUT=ROOT/'output/onboard_dashboard/phone-live-vision-20261026';OUT.mkdir(parents=True,exist_ok=True)
CACHE=Path.home()/'.cache/zhixing-android-tools';ADB=ROOT/'tmp/android-tools/platform-tools/adb.exe'
JDK=Path(r'C:\Program Files\BellSoft\LibericaJDK-17')/'bin'
stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
work=Path.home()/'.cache'/('zhixing-phone-vision-check-'+stamp);classes=work/'classes';classes.mkdir(parents=True,exist_ok=False);dex=work/'dex';dex.mkdir()
android=next(CACHE.glob('platform-33-ext3_r03/**/android.jar'));d8=next(CACHE.glob('build-tools_r35_windows/**/lib/d8.jar'))
def run(*a):return subprocess.run([str(x) for x in a],capture_output=True,timeout=90,check=True)
if run(ADB,'-s','0123456789ABCDEF','shell','getprop','ro.board.platform').stdout.decode().strip()!='mt6739':raise RuntimeError('Configured phone absent')
run(JDK/'javac.exe','-encoding','UTF-8','--release','8','-cp',android,'-d',classes,*[HERE/'android'/name for name in ('PhoneColorTracker.java','PhoneVision.java','FrameCadence.java')],HERE/'checks/PhoneVisionChecks.java')
jar=work/'checks.jar';run(JDK/'jar.exe','cf',jar,'-C',classes,'.')
run(JDK/'java.exe','-cp',d8,'com.android.tools.r8.D8','--min-api','26','--lib',android,'--output',dex,jar)
remote='/data/local/tmp/zhixing_phone_vision_checks_'+stamp;run(ADB,'-s','0123456789ABCDEF','shell','mkdir',remote);run(ADB,'-s','0123456789ABCDEF','push',dex/'classes.dex',remote+'/classes.dex')
r=run(ADB,'-s','0123456789ABCDEF','shell','CLASSPATH='+remote+'/classes.dex app_process /system/bin cn.zhixing.dashboard.PhoneVisionChecks')
report=json.loads(r.stdout.decode().strip());assert report['checks']>=40 and report['phase_selected_frames']>report['legacy_selected_frames']
(OUT/'android-controlled-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
