"""Run the real V3 controller, pure Java identity gate and PC broker, fake IO."""
from pathlib import Path
import importlib.util
import json
import subprocess
import unittest
import test_mecanum as old

ROOT, SW = old.ROOT, old.SW
FW = SW / 'build/r1_mecanum_groundmap'
SRC = FW / 'source-snapshot'
OUT = ROOT / 'output/onboard_dashboard/mecanum-groundmap-20261107/checks'

EXTRA_C = r'''
 /* Both public axes must use the empirical ground profile. The canonical
    mixer above is tested separately and remains the standard X model. */
 for(f=-250;f<=250;f+=50)for(x=-250;x<=250;x+=50)for(r=-250;r<=250;r+=50){
   int32_t canonical[4],swapped_axes[4];unsigned gen;uint32_t t=20000+checks;
   remote_drive_stop(5);healthy(t);memset((void*)motor_speed_values,0,sizeof(motor_speed_values));
   command("DRIVE_ARM",t);CHECK(sscanf(response,"DRIVE_ARMED,%u",&gen)==1);
   snprintf(q,sizeof(q),"DRIVE_VECTOR,%u,1,%d,%d,%d",gen,f,x,r);command(q,t);
   CHECK(!strcmp(response,"DRIVE_VECTOR_ACCEPTED\n"));remote_drive_poll(t);
   CHECK(mecanum_mix(f,x,r,canonical));CHECK(mecanum_mix(f,r,x,swapped_axes));
   CHECK(wheel_targets[0]==4*canonical[0]);CHECK(wheel_targets[1]==4*canonical[3]);
   CHECK(wheel_targets[2]==4*canonical[2]);CHECK(wheel_targets[3]==4*canonical[1]);
   for(i=0;i<4;i++){CHECK(wheel_targets[i]==4*swapped_axes[i]);CHECK(last_write[i]==wheel_outputs[i]);}
   /* Polling again must not toggle the permutation. */
   healthy(t+20);remote_drive_poll(t+20);
   for(i=0;i<4;i++)CHECK(wheel_targets[i]==4*swapped_axes[i]);
 }
 remote_drive_stop(5);healthy(100000);memset((void*)motor_speed_values,0,sizeof(motor_speed_values));command("DRIVE_ARM",100000);
 {unsigned gen;CHECK(sscanf(response,"DRIVE_ARMED,%u",&gen)==1);
 snprintf(q,sizeof(q),"DRIVE_SET,%u,1,40,20",gen);command(q,100020);CHECK(!strcmp(response,"DRIVE_SET_ACCEPTED\n"));
 healthy(100020);remote_drive_poll(100020);CHECK(wheel_targets[0]==160&&wheel_targets[1]==80&&wheel_targets[2]==80&&wheel_targets[3]==160);
 task_owner=1;snprintf(q,sizeof(q),"DRIVE_VECTOR,%u,2,0,100,0",gen);command(q,100040);CHECK(!strcmp(response,"ERR,LINE_TASK_OWNS_DRIVE\n"));
 CHECK(remote_drive_task_set(100040,30,50));healthy(100040);remote_drive_poll(100040);CHECK(wheel_targets[0]==120&&wheel_targets[1]==200&&wheel_targets[2]==200&&wheel_targets[3]==120);
 remote_drive_stop(5);task_owner=0;}
 command("DRIVE_CHASSIS",100050);CHECK(!strcmp(response,"DRIVE_CHASSIS,MECANUM_GROUND_MAP,SWAP_M2_M4,250,600\n"));
'''

LAYOUT_JAVA = r'''
package cn.zhixing.dashboard;
public class LayoutHarness {
 public static void main(String[] args){
  String[] ids={"DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_MECANUM_V2_20261107,1","DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_MECANUM_V3_20261107,1","unknown"};
  String[] layouts={"DRIVE_CHASSIS,MECANUM_X,FL_RL_FR_RR,250,600","DRIVE_CHASSIS,MECANUM_GROUND_MAP,SWAP_M2_M4,250,600","unknown"};
  for(int i=0;i<3;i++)for(int j=0;j<3;j++)if(MecanumLayout.matches(ids[i],layouts[j])!=(i==j&&i<2))throw new AssertionError(i+":"+j);
  if(MecanumLayout.matches(null,null))throw new AssertionError("null");
  System.out.println("{\"result\":\"PASS\",\"identity_layout_pairs\":10}");
 }
}
'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    c = old.C.replace('"DRIVE_SET,1,2,1,1"', '"DRIVE_VECTOR,1,2,0,0,251"')
    c = c.replace('static unsigned checks,stops,writes;', 'static unsigned checks,stops,writes;static int32_t last_write[4];\nstatic int task_owner;int line_task_running(void){return task_owner;}\nextern int remote_drive_task_set(uint32_t,int,int);')
    c = c.replace('++writes;return 1;', '++writes;last_write[0]=a;last_write[1]=b;last_write[2]=c;last_write[3]=d;return 1;')
    c = c.replace('wheel_targets[0]==400&&wheel_targets[1]==-400&&wheel_targets[2]==-400&&wheel_targets[3]==400', 'wheel_targets[0]==400&&wheel_targets[1]==400&&wheel_targets[2]==-400&&wheel_targets[3]==-400')
    c = c.replace(' CHECK(stops>0&&writes>0);', EXTRA_C + '\n CHECK(stops>0&&writes>0);')
    p, exe = OUT / 'groundmap-harness.c', OUT / 'groundmap-harness.exe'
    p.write_text(c, encoding='utf-8')
    cc = ROOT / 'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe'
    subprocess.run([str(cc), '-I'+str(SRC), str(p), str(SRC/'remote_drive.c'), str(SRC/'wheel_control.c'), str(SRC/'mecanum_mix.c'), '-o', str(exe)], check=True)
    result = subprocess.run([str(exe)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    report = {'mcu_host': json.loads(result.stdout)}
    work = OUT / 'jvm'; work.mkdir(exist_ok=True)
    stub = work / 'SystemClock.java'; stub.write_text('package android.os;public final class SystemClock{public static long elapsedRealtime(){return System.nanoTime()/1000000;}}', encoding='utf-8')
    harness = work / 'MecanumHarness.java'; harness.write_text(old.JAVA, encoding='utf-8')
    layout = work / 'LayoutHarness.java'; layout.write_text(LAYOUT_JAVA, encoding='utf-8')
    java = Path('C:/Program Files/BellSoft/LibericaJDK-17/bin')
    jar = ROOT / 'tmp/realtime-harness/json.jar'; ui = SW / 'debug_ui/android'
    sources = [stub, harness, layout, *[ui / n for n in ('GimbalSettings.java','ControlBroker.java','DriveBroker.java','BoardReplyException.java','MecanumLayout.java')]]
    subprocess.run([str(java/'javac.exe'), '-encoding','UTF-8','-cp',str(jar),'-d',str(work), *map(str,sources)], check=True)
    for name,key in [('MecanumHarness','android_jvm'),('cn.zhixing.dashboard.LayoutHarness','android_layout')]:
        result = subprocess.run([str(java/'java.exe'),'-cp',str(work)+';'+str(jar),name],capture_output=True,text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        report[key] = json.loads(result.stdout)
    import test_mecanum_pc as pc
    spec = importlib.util.spec_from_file_location('groundmap_pc', SW/'debug_ui/speed_server.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); pc.original.module = m
    setup = pc.Mecanum.setUp
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(pc.original.Protocol)])
    for identity in m.MECANUM_LAYOUTS:
        def current_setup(self, identity=identity):
            setup(self); self.b.identity = identity
        cls = type('Protocol_'+identity, (pc.Mecanum,), {'setUp': current_setup})
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    results = unittest.TextTestRunner(verbosity=1).run(suite)
    assert results.wasSuccessful()
    report['pc'] = {'result':'PASS','cases':results.testsRun,'hardware_io':False}
    meta = json.loads((FW/'build_result.json').read_text(encoding='utf-8'))
    report.update(result='PASS',binary_sha256=meta['binary_sha256'],physical_acceptance='NOT_RUN')
    for p in (OUT/'results.json',FW/'controller-host-verification.json'):
        p.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
