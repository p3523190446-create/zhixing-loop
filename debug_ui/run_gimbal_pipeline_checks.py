"""Compile production image/control classes against an isolated JVM clock."""
from pathlib import Path
import datetime,json,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OUT=ROOT/'output/onboard_dashboard/gimbal-handoff-20261107'
work=Path.home()/'.cache'/('zhixing-pipeline-'+datetime.datetime.now().strftime('%Y%m%d%H%M%S'));work.mkdir()
clock=work/'SystemClock.java';clock.write_text('package android.os; public class SystemClock {public static long elapsedRealtime(){return System.nanoTime()/1000000;}}',encoding='utf-8')
jar=ROOT/'tmp/realtime-harness/json.jar';jdk=Path(r'C:\Program Files\BellSoft\LibericaJDK-17')/'bin'
src=[HERE/'android'/s for s in ['GimbalSettings.java','GimbalFollower.java','ControlBroker.java','PhoneVision.java','PhoneColorTracker.java','FollowInterlock.java']]
src += [HERE/'checks/GimbalCalibrationChecks.java',HERE/'checks/GimbalImagePipelineChecks.java',clock]
subprocess.run([str(jdk/'javac.exe'),'-encoding','UTF-8','--release','8','-cp',str(jar),'-d',str(work),*map(str,src)],check=True,capture_output=True)
r=subprocess.run([str(jdk/'java.exe'),'-cp',str(work)+';'+str(jar),'cn.zhixing.dashboard.GimbalImagePipelineChecks'],check=True,capture_output=True,text=True)
d=json.loads(r.stdout.strip().splitlines()[-1]);(OUT/'image-pipeline-checks.json').write_text(json.dumps(d,indent=2),encoding='utf-8');print(json.dumps(d))
