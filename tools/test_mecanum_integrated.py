"""Use the existing control harness against merged MCU and current Android sources."""
from pathlib import Path
import json,subprocess,sys,unittest
import test_mecanum as old
ROOT=old.ROOT;SW=old.SW;SRC=SW/'board/r1_mecanum_integrated';BASE=SW/'build/r1_line_continuous/source-snapshot'
OUT=ROOT/'output/onboard_dashboard/mecanum-live-20261107/checks';OUT.mkdir(parents=True,exist_ok=True)

def main():
 c=old.C.replace('"DRIVE_SET,1,2,1,1"','"DRIVE_VECTOR,1,2,0,0,251"')
 c=c.replace('static unsigned checks,stops,writes;', 'static unsigned checks,stops,writes;\nstatic int task_owner;int line_task_running(void){return task_owner;}\nextern int remote_drive_task_set(uint32_t,int,int);')
 c=c.replace(' CHECK(stops>0&&writes>0);',r'''
 healthy(12000);memset((void*)motor_speed_values,0,sizeof(motor_speed_values));command("DRIVE_ARM",12000);
 {unsigned gen;CHECK(sscanf(response,"DRIVE_ARMED,%u",&gen)==1);
 snprintf(q,sizeof(q),"DRIVE_SET,%u,1,40,20",gen);command(q,12020);CHECK(!strcmp(response,"DRIVE_SET_ACCEPTED\n"));
 healthy(12020);remote_drive_poll(12020);CHECK(wheel_targets[0]==160&&wheel_targets[1]==160&&wheel_targets[2]==80&&wheel_targets[3]==80);
 task_owner=1;snprintf(q,sizeof(q),"DRIVE_VECTOR,%u,2,0,100,0",gen);command(q,12040);CHECK(!strcmp(response,"ERR,LINE_TASK_OWNS_DRIVE\n"));
 CHECK(remote_drive_task_set(12040,30,50));healthy(12040);remote_drive_poll(12040);CHECK(wheel_targets[0]==120&&wheel_targets[1]==120&&wheel_targets[2]==200&&wheel_targets[3]==200);
 remote_drive_stop(5);task_owner=0;}
 CHECK(stops>0&&writes>0);''')
 p=OUT/'merged-harness.c';p.write_text(c,encoding='utf-8');exe=OUT/'merged-harness.exe';cc=ROOT/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe'
 subprocess.run([str(cc),'-I'+str(SRC),'-I'+str(BASE),str(p),str(SRC/'remote_drive.c'),str(SRC/'wheel_control.c'),str(SRC/'mecanum_mix.c'),'-o',str(exe)],check=True)
 result=subprocess.run([str(exe)],capture_output=True,text=True);assert result.returncode==0,result.stdout+result.stderr
 report={'mcu_host':json.loads(result.stdout)}
 work=OUT/'jvm';work.mkdir(exist_ok=True);stub=work/'SystemClock.java';stub.write_text('package android.os;public final class SystemClock{public static long elapsedRealtime(){return System.nanoTime()/1000000;}}',encoding='utf-8')
 p=work/'MecanumHarness.java';p.write_text(old.JAVA,encoding='utf-8');java=Path('C:/Program Files/BellSoft/LibericaJDK-17/bin');jar=ROOT/'tmp/realtime-harness/json.jar';ui=SW/'debug_ui/android'
 subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-cp',str(jar),'-d',str(work),str(stub),str(ui/'GimbalSettings.java'),str(ui/'ControlBroker.java'),str(ui/'DriveBroker.java'),str(ui/'BoardReplyException.java'),str(p)],check=True)
 result=subprocess.run([str(java/'java.exe'),'-cp',str(work)+';'+str(jar),'MecanumHarness'],capture_output=True,text=True);assert result.returncode==0,result.stdout+result.stderr
 report['android_jvm']=json.loads(result.stdout)
 # Existing ordinary-PC suite and added lateral/compatibility cases on CURRENT code.
 import test_mecanum_pc as pc
 import importlib.util
 spec=importlib.util.spec_from_file_location('current_mecanum_pc',SW/'debug_ui/speed_server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 pc.original.module=m
 setup=pc.Mecanum.setUp
 def current_setup(self):setup(self);self.b.identity='R1_DRIVE_STARTUP_MANUAL_MECANUM_V2_20261107'
 pc.Mecanum.setUp=current_setup
 suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(pc.original.Protocol),unittest.defaultTestLoader.loadTestsFromTestCase(pc.Mecanum)])
 results=unittest.TextTestRunner(verbosity=1).run(suite);assert results.wasSuccessful()
 report['pc']={'result':'PASS','cases':results.testsRun,'hardware_io':False}
 (OUT/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 fw=SW/'build/r1_mecanum_integrated';meta=json.loads((fw/'build_result.json').read_text(encoding='utf-8'))
 (fw/'controller-host-verification.json').write_text(json.dumps(dict(result='PASS',binary_sha256=meta['binary_sha256'],**report),indent=2)+'\n',encoding='utf-8')
 print(json.dumps(report))

if __name__=='__main__':main()
