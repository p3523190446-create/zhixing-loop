"""Execute the actual format inspector against the failing fixture on Android."""
from pathlib import Path
import datetime,json,os,subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
OUT=ROOT/'output/onboard_dashboard/camera-compat-20261026/v0251'
CACHE=Path.home()/'.cache/zhixing-android-tools'
ADB=ROOT/'tmp/android-tools/platform-tools/adb.exe'
JDK=Path(r'C:\Program Files\BellSoft\LibericaJDK-17')/'bin'
stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
work=Path.home()/'.cache'/('zhixing-format-check-'+stamp)
classes=work/'classes';classes.mkdir(parents=True,exist_ok=False)
dex=work/'dex';dex.mkdir()
android=next(CACHE.glob('platform-33-ext3_r03/**/android.jar'))
d8=next(CACHE.glob('build-tools_r35_windows/**/lib/d8.jar'))
def run(*a):return subprocess.run([str(x) for x in a],capture_output=True,timeout=60,check=True)
identity=run(ADB,'-s','0123456789ABCDEF','shell','getprop','ro.board.platform').stdout.decode().strip()
if identity!='mt6739':raise RuntimeError('Not the configured phone')
run(JDK/'javac.exe','-encoding','UTF-8','--release','8','-cp',android,'-d',classes,
    HERE/'android/CameraFormatInfo.java',HERE/'checks/CameraFormatChecks.java')
jar=work/'checks.jar'
run(JDK/'jar.exe','cf',jar,'-C',classes,'.')
run(JDK/'java.exe','-cp',d8,'com.android.tools.r8.D8','--min-api','26','--lib',android,'--output',dex,jar)
remote='/data/local/tmp/zhixing_format_checks_'+stamp
run(ADB,'-s','0123456789ABCDEF','shell','mkdir',remote)
run(ADB,'-s','0123456789ABCDEF','push',dex/'classes.dex',remote+'/classes.dex')
run(ADB,'-s','0123456789ABCDEF','push',OUT/'actual-original-native-formats.json',remote+'/actual.json')
result=run(ADB,'-s','0123456789ABCDEF','shell','CLASSPATH='+remote+'/classes.dex app_process /system/bin cn.zhixing.dashboard.CameraFormatChecks '+remote+'/actual.json')
text=result.stdout.decode('utf-8','replace').strip()
if 'PASS 16 checks' not in text:raise RuntimeError(text)
report=dict(result=text,real_android_json=True,real_failing_fixture=True,camera_opened=False,controller_commands_sent=False)
(OUT/'actual-parser-regression.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
