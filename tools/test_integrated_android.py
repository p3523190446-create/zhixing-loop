"""JVM checks of actual Android broker/codec sources; no USB or motor commands."""
from pathlib import Path
import subprocess, json
ROOT=Path(__file__).resolve().parents[2]
out=ROOT/'output/onboard_dashboard/integrated-v014'
work=out/'jvm';work.mkdir(exist_ok=True)
stub=work/'SystemClock.java'
stub.write_text('package android.os; public final class SystemClock {public static long elapsedRealtime(){return System.nanoTime()/1000000;}}',encoding='utf8')
harness=work/'IntegrationHarness.java'
harness.write_text(r'''
import cn.zhixing.dashboard.*;import org.json.*;import java.util.*;import java.util.concurrent.*;
public class IntegrationHarness {
 static int checks;static void check(boolean ok,String name){if(!ok)throw new AssertionError(name);checks++;}
 public static void main(String[] args)throws Exception {
  DriveBroker b=new DriveBroker();List<String> sent=new ArrayList<>();
  ControlBroker.Exchange link=(command,prefix)->{sent.add(command);if(command.equals("DRIVE_ARM"))return "DRIVE_ARMED,7";if(command.equals("DRIVE_STATUS"))return "DRIVE,1000,1,0,7,0,0,0,0,0";return prefix;};
  CompletableFuture<JSONObject> start=CompletableFuture.supplyAsync(()->{try{return b.submit("start",new JSONObject().put("bench_confirmed",true));}catch(Exception e){throw new RuntimeException(e);}});
  while(!start.isDone()){b.pump(link);Thread.sleep(1);}String sid=start.get().getString("session");
  check(b.publicState().getBoolean("active"),"confirmed start owns session");
  b.observe("DRIVE,990,0,0,6,0,0,0,0,0");check(b.publicState().getBoolean("active"),"older pre-start sample cannot revoke new owner");
  b.observe("DRIVE,1010,1,0,7,0,0,0,0,0");check(b.publicState().getBoolean("active"),"current matching sample retains owner");
  b.observe("DRIVE,1020,0,0,7,0,0,0,1,600");check(!b.publicState().getBoolean("active"),"actual MCU expiry revokes owner");
  check(sent.size()==2,"observing telemetry never sends motion or keepalive");
  Map<String,String> rows=new HashMap<>();rows.put("DRIVE_ACTUATORS","ACTUATORS,100,101,102,103,104,96,96,96,96,3");rows.put("DRIVE_STATUS","DRIVE,100,1,1,7,2,100,100,0,0");
  JSONObject decoded=TelemetryCodec.decode(rows,20,true,null);
  check(decoded.getJSONArray("applied_pwm").getInt(3)==104,"four actual PWM values decoded");
  check(decoded.getJSONArray("speed_targets").getInt(0)==96,"speed target decoded");
  check(decoded.getInt("controller_fault")==3,"controller fault decoded");
  check(decoded.getBoolean("motion_active"),"MCU moving state decoded");
  check(!TelemetryCodec.decode(rows,3000,true,"stale").has("applied_pwm"),"stale actuator values not displayed");
  System.out.println("{\"checks\":"+checks+",\"result\":\"PASS\",\"hardware_io\":false}");
 }
}
''',encoding='utf8')
java=Path('C:/Program Files/BellSoft/LibericaJDK-17/bin')
jar=ROOT/'tmp/realtime-harness/json.jar';ui=ROOT/'知行回路软件/debug_ui/android'
subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-cp',str(jar),'-d',str(work),str(stub),str(ui/'ControlBroker.java'),str(ui/'DriveBroker.java'),str(ui/'TelemetryCodec.java'),str(harness)],check=True)
result=subprocess.run([str(java/'java.exe'),'-cp',str(work)+';'+str(jar),'IntegrationHarness'],capture_output=True,text=True,check=True)
data=json.loads(result.stdout);(out/'android-jvm-checks.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf8');print(result.stdout)
