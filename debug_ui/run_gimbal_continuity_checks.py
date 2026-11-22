"""Production NV21 and controller checks, with a JVM clock and fake MCU."""
from pathlib import Path
import datetime,json,os,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OUT=Path(os.environ['ZX_GIMBAL_CHECK_OUT']);OUT.mkdir(parents=True,exist_ok=True)
work=Path.home()/'.cache'/('zhixing-continuity-'+datetime.datetime.now().strftime('%Y%m%d%H%M%S%f'));work.mkdir()
clock=work/'SystemClock.java';clock.write_text('package android.os; public class SystemClock {public static long elapsedRealtime(){return System.nanoTime()/1000000;}}',encoding='utf-8')
jar=ROOT/'tmp/realtime-harness/json.jar';jdk=Path(r'C:\Program Files\BellSoft\LibericaJDK-17')/'bin'
src=[HERE/'android'/s for s in ['GimbalSettings.java','GimbalFollower.java','ControlBroker.java','PhoneVision.java','PhoneColorTracker.java','FollowInterlock.java','FrameCadence.java']]
src += [HERE/'checks'/s for s in ['GimbalCalibrationChecks.java','GimbalImagePipelineChecks.java','GimbalContinuityChecks.java','PhoneVisionChecks.java']]+[clock]
subprocess.run([str(jdk/'javac.exe'),'-encoding','UTF-8','--release','8','-cp',str(jar),'-d',str(work),*map(str,src)],check=True)
reports={}
for name in ['GimbalContinuityChecks','PhoneVisionChecks','GimbalImagePipelineChecks']:
 r=subprocess.run([str(jdk/'java.exe'),'-cp',str(work)+';'+str(jar),'cn.zhixing.dashboard.'+name],capture_output=True,text=True,encoding='utf-8')
 (OUT/(name+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
 if r.returncode:raise RuntimeError(name+': '+r.stdout+r.stderr)
 reports[name]=json.loads(r.stdout.strip().splitlines()[-1])
(OUT/'continuity-checks.json').write_text(json.dumps(reports,indent=2),encoding='utf-8');print(json.dumps(reports))
