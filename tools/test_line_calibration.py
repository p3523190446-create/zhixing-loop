"""Production calibration service on JVM, deterministic fake clock/MCU, no USB."""
from pathlib import Path
import subprocess,json
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'output/onboard_dashboard/phone-line-calibration-20261027/jvm';OUT.mkdir(parents=True,exist_ok=True)
JAVA=r'''
import cn.zhixing.dashboard.*;import org.json.*;import java.util.*;
public class LineCalibrationHarness {
 static int checks;static long frame=1;static String persisted,wire;static boolean badReadback,failedStore;static int sets;
 static void ck(boolean v){checks++;if(!v)throw new AssertionError("check "+checks);}
 static ControlBroker.Exchange link=(c,p)->{if(c.equals("LINE_TASK_CAL_CAPS"))return "LINE_TASK_CAL_CAPS,1,8";if(c.startsWith("LINE_TASK_CAL_SET,")){sets++;String[] v=c.split(",");int[] f=new int[8],b=new int[8];for(int i=0;i<8;i++){f[i]=Integer.parseInt(v[i+1]);b[i]=Integer.parseInt(v[i+9]);}long id=LineCalibration.fingerprint(f,b);wire="LINE_TASK_CAL,"+id+c.substring(17);return "LINE_TASK_CAL_SAVED,"+id;}if(c.equals("LINE_TASK_CAL_GET"))return badReadback?"LINE_TASK_CAL,0":wire;throw new AssertionError(c);};
 static JSONObject live(int value)throws Exception{return new JSONObject().put("connected",true).put("motion_active",false).put("line",new JSONObject().put("valid",true).put("age_ms",5).put("analog_frames",frame).put("digital_frames",frame).put("uart_errors",0).put("overflows",22).put("raw",new JSONArray(new int[]{value,value+1,value+2,value+3,value+4,value+5,value+6,value+7})));}
 static LineCalibration make()throws Exception{return new LineCalibration(null,j->{if(failedStore)throw new Exception("store failed");persisted=j;});}
 static void reject(LineCalibration c,String op,boolean idle,JSONObject live)throws Exception{boolean failed=false;try{c.command(op,idle,live);}catch(Exception e){failed=true;}ck(failed);}
 static void capture(LineCalibration c,String surface,int value)throws Exception{c.command(surface,true,live(value));for(int i=0;i<6;i++){android.os.SystemClock.now+=1000;frame++;c.observe(live(value+(i%2)*2),true);}}
 static void pair(LineCalibration c)throws Exception{capture(c,"floor",1200);capture(c,"black",3200);ck(c.state().getBoolean("black_done"));}
 public static void main(String[] args)throws Exception{
  LineCalibration c=make();reject(c,"floor",true,live(1200));c.connect(link);ck(!c.ready());reject(c,"black",true,live(3200));reject(c,"floor",false,live(1200));reject(c,"floor",true,live(1200).put("connected",false));
  c.command("floor",true,live(1200));for(int i=0;i<4;i++){android.os.SystemClock.now+=400;c.observe(live(1200),true);}ck(c.state().getInt("samples")==0);c.command("cancel",false,live(1200));ck(!c.busy());
  c.command("floor",true,live(1200));frame++;c.observe(live(1200).put("motion_active",true),true);ck(!c.busy()&&!c.state().getBoolean("floor_done"));
  pair(c);c.command("save",true,live(3200));ck(c.busy()&&!c.ready());c.pump(link,true);ck(c.ready()&&persisted!=null&&sets==1);ck(c.state().getJSONObject("profile").getJSONArray("floor").getInt(0)==1202);
  String saved=persisted;c.disconnect();ck(!c.ready()&&c.state().getBoolean("saved"));c.connect(link);ck(c.ready()&&sets==2);LineCalibration restored=new LineCalibration(saved,j->{});restored.connect(link);ck(restored.ready());
  capture(c,"floor",1200);capture(c,"black",1300);ck(!c.state().getBoolean("black_done")&&c.ready());reject(c,"save",true,live(1300));
  c.command("black",true,live(3200));for(int i=0;i<6;i++){android.os.SystemClock.now+=1000;frame++;c.observe(live(i%2==0?3000:3500),true);}ck(!c.state().getBoolean("black_done"));
  capture(c,"black",3200);c.command("save",true,live(3200));badReadback=true;c.pump(link,true);ck(!c.ready()&&persisted.equals(saved));badReadback=false;
  c.command("save",true,live(3200));failedStore=true;c.pump(link,true);ck(!c.ready()&&persisted.equals(saved));failedStore=false;c.command("save",true,live(3200));c.pump(link,true);ck(c.ready());
  c.command("floor",true,live(1200));android.os.SystemClock.now+=3000;frame++;c.observe(live(1200),true);ck(!c.busy());
  c.command("floor",true,live(1200));frame++;JSONObject e=live(1200);e.getJSONObject("line").put("uart_errors",1);c.observe(e,true);ck(!c.busy());
  c.command("floor",true,live(1200));frame--;c.observe(live(1200),true);ck(!c.busy());
  c.command("floor",true,live(1200));c.disconnect();ck(!c.busy()&&!c.ready());
  boolean corrupt=false;try{new LineCalibration(new JSONObject(saved).put("id",0).toString(),j->{});}catch(Exception e2){corrupt=true;}ck(corrupt);
  System.out.println("{\"result\":\"PASS\",\"assertions\":"+checks+",\"hardware_io\":false,\"profile_id\":"+new JSONObject(saved).getLong("id")+"}");
 }
}
'''
(OUT/'SystemClock.java').write_text('package android.os;public class SystemClock{public static long now=1000;public static long elapsedRealtime(){return now;}}',encoding='utf-8')
(OUT/'LineCalibrationHarness.java').write_text(JAVA,encoding='utf-8')
# Only the Exchange interface is needed; the production class under test is unchanged.
(OUT/'ControlBroker.java').write_text('package cn.zhixing.dashboard;public class ControlBroker{public interface Exchange{String call(String command,String prefix)throws Exception;}}',encoding='utf-8')
jdk=Path('C:/Program Files/Java/jdk-21.0.10/bin');jar=ROOT/'tmp/realtime-harness/json.jar'
subprocess.run(list(map(str,[jdk/'javac.exe','-encoding','UTF-8','-cp',jar,'-d',OUT,OUT/'SystemClock.java',OUT/'ControlBroker.java',ROOT/'知行回路软件/debug_ui/android/LineCalibration.java',OUT/'LineCalibrationHarness.java'])),check=True)
p=subprocess.run([str(jdk/'java.exe'),'-cp',str(OUT)+';'+str(jar),'LineCalibrationHarness'],capture_output=True,text=True,encoding='utf-8')
if p.returncode:raise RuntimeError(p.stdout+p.stderr)
r=json.loads(p.stdout);(OUT.parent/'calibration-tests.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r))
