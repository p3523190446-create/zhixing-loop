"""Test the production Android broker on JVM with a fake MCU, never USB."""
from pathlib import Path
import subprocess,json
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'output/onboard_dashboard/phone-line-control-20261026/jvm';OUT.mkdir(parents=True,exist_ok=True)
JAVA=r'''
import cn.zhixing.dashboard.*;import org.json.*;import java.util.*;import java.util.concurrent.*;
public class LineTaskHarness {
 static int checks,starts,stops,beats;static boolean armed,badConfig,lostStart;static List<String> commands=new ArrayList<>();
 static void ck(boolean v){checks++;if(!v)throw new AssertionError("case "+checks);}
 static ControlBroker.Exchange link=(c,p)->{commands.add(c);
  if(c.startsWith("LINE_TASK_CONFIG,"))return badConfig?"ERR,LINE_TASK_CONFIG":"LINE_TASK_CONFIGURED";
  if(c.equals("LINE_TASK_START")){armed=true;starts++;return lostStart?"WRONG":"LINE_TASK_STARTED";}
  if(c.equals("LINE_TASK_STOP")){armed=false;stops++;return "LINE_TASK_STOPPED";}
  if(c.equals("LINE_TASK_KEEPALIVE")){beats++;return armed?"LINE_TASK_ALIVE":"ERR,LINE_TASK_NOT_RUNNING";}
  if(c.equals("LINE_TASK_STATUS"))return "LINE_TASK_STATUS,60000,"+(armed?1:0)+",0,0,0,0,1,0,40,5000";
  throw new Exception("unexpected fake exchange "+c);
 };
 static JSONObject body()throws Exception{return new JSONObject().put("x1_left",1).put("branch",0).put("speed",40).put("duration_ms",5000);}
 static CompletableFuture<JSONObject> submit(LineTaskBroker b,String action,JSONObject body){return CompletableFuture.supplyAsync(()->{try{return b.submit(action,body);}catch(Exception e){throw new CompletionException(e);}});}
 static JSONObject call(LineTaskBroker b,String action,JSONObject body)throws Exception{CompletableFuture<JSONObject> task=submit(b,action,body);long until=System.currentTimeMillis()+2300;while(!task.isDone()&&System.currentTimeMillis()<until){b.pump(link);Thread.sleep(1);}return task.get(1,TimeUnit.SECONDS);}
 static void reject(LineTaskBroker b,String action,JSONObject body)throws Exception{boolean fail=false;try{call(b,action,body);}catch(Exception e){fail=true;}ck(fail);}
 public static void main(String[] args)throws Exception{
  LineTaskBroker b=new LineTaskBroker();String sid=call(b,"start",body()).getString("session");ck(armed&&b.active()&&starts==1);ck(commands.get(0).equals("LINE_TASK_CONFIG,1,0,40,5000"));
  call(b,"heartbeat",new JSONObject().put("session",sid));ck(beats==1);
  int old=stops;reject(b,"heartbeat",new JSONObject().put("session","wrong"));ck(armed&&b.active()&&stops==old);
  reject(b,"start",body());ck(armed&&stops==old);call(b,"stop",new JSONObject());ck(!armed&&!b.active());
  reject(b,"start",body().put("x1_left",0));ck(starts==1);reject(b,"start",body().put("speed",101));reject(b,"start",body().put("branch",5));reject(b,"start",body().put("duration_ms",10001));reject(b,"start",body().put("duration_ms",0));
  sid=call(b,"start",body()).getString("session");b.observe("LINE_TASK_STATUS,59000,0,0,0,0,0,1,0,40,5000");ck(b.active());b.observe("LINE_TASK_STATUS,60001,4,6,1,0,0,1,0,40,5000");ck(!b.active());armed=false;
  sid=call(b,"start",body()).getString("session");android.os.SystemClock.offset=500;b.pump(link);ck(!armed&&!b.active());android.os.SystemClock.offset=0;
  int before=starts;CompletableFuture<JSONObject> pending=submit(b,"start",body());Thread.sleep(15);CompletableFuture<JSONObject> stop=submit(b,"stop",new JSONObject());Thread.sleep(15);b.pump(link);ck(stop.get(1,TimeUnit.SECONDS).getBoolean("stopped"));boolean rejected=false;try{pending.get(1,TimeUnit.SECONDS);}catch(Exception e){rejected=true;}ck(rejected&&starts==before&&!armed);
  pending=submit(b,"start",body());Thread.sleep(15);android.os.SystemClock.offset=1000;b.pump(link);rejected=false;try{pending.get(1,TimeUnit.SECONDS);}catch(Exception e){rejected=true;}ck(rejected&&starts==before);android.os.SystemClock.offset=0;
  badConfig=true;armed=true;old=stops;reject(b,"start",body());ck(armed&&stops==old);badConfig=false;armed=false;
  lostStart=true;reject(b,"start",body());ck(!armed&&!b.active());lostStart=false;
  sid=call(b,"start",body()).getString("session");b.disconnect();ck(!b.active());armed=false;reject(b,"heartbeat",new JSONObject().put("session",sid));
  sid=call(b,"start",body().put("branch",4).put("duration_ms",0)).getString("session");ck(commands.contains("LINE_TASK_CONFIG,1,4,40,0")&&armed);call(b,"stop",new JSONObject());ck(!armed);
  ck(BoardReplyException.rejects("LINE_TASK_START","ERR,LINE_TASK_GROUND_NOT_ACCEPTED_OR_BUSY"));ck(!BoardReplyException.rejects("MPU_RAW","ERR,OTHER"));
  System.out.println("{\"result\":\"PASS\",\"assertions\":"+checks+",\"hardware_io\":false}");
 }
}
'''
(OUT/'SystemClock.java').write_text('package android.os; public final class SystemClock {public static long offset;public static long elapsedRealtime(){return System.nanoTime()/1000000+offset;}}',encoding='utf-8')
(OUT/'LineTaskHarness.java').write_text(JAVA,encoding='utf-8');jdk=Path('C:/Program Files/BellSoft/LibericaJDK-17/bin');jar=ROOT/'tmp/realtime-harness/json.jar';src=ROOT/'知行回路软件/debug_ui/android'
subprocess.run(list(map(str,[jdk/'javac.exe','-encoding','UTF-8','-cp',jar,'-d',OUT,OUT/'SystemClock.java',src/'GimbalSettings.java',src/'ControlBroker.java',src/'LineTaskBroker.java',src/'BoardReplyException.java',OUT/'LineTaskHarness.java'])),check=True)
p=subprocess.run([str(jdk/'java.exe'),'-cp',str(OUT)+';'+str(jar),'LineTaskHarness'],capture_output=True,text=True)
if p.returncode:raise RuntimeError(p.stdout+p.stderr)
r=json.loads(p.stdout);(OUT.parent/'broker-tests.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r))
