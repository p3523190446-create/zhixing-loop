package cn.zhixing.dashboard;
import android.os.SystemClock;
import org.json.*;
import java.io.*;
import java.util.concurrent.*;

/** Explicit local unit checks; fake exchange, no UsbManager, no device writes. */
public final class ControlSelfCheck {
  private static class Fake implements ControlBroker.Exchange {boolean active;long starts;int yaw=1500,pitch=1500;public String call(String cmd,String prefix){if(cmd.equals("GIMBAL_STATUS"))return "GIMBAL,1000,1,"+(active?1:0)+","+(active?5:0)+","+(active?yaw:0)+","+(active?pitch:0)+","+starts+",0,1000000,1000000";if(cmd.equals("GIMBAL_MANUAL_START")){active=true;starts++;yaw=pitch=1500;return "GIMBAL_MANUAL_STARTED";}if(cmd.equals("GIMBAL_STOP")){active=false;return "GIMBAL_STOPPED";}if(cmd.startsWith("GIMBAL_SET,")){String[] f=cmd.split(",");yaw=Integer.parseInt(f[1]);pitch=Integer.parseInt(f[2]);return "GIMBAL_SET_ACCEPTED";}if(cmd.equals("GIMBAL_KEEPALIVE"))return "GIMBAL_ALIVE";throw new IllegalArgumentException("unexpected fake command");}}
  private static JSONObject call(ControlBroker broker,Fake fake,String action,JSONObject body)throws Exception{FutureTask<JSONObject> future=new FutureTask<>(()->broker.submit(action,body));new Thread(future).start();long end=SystemClock.elapsedRealtime()+2800;while(!future.isDone()&&SystemClock.elapsedRealtime()<end){broker.pump(fake);SystemClock.sleep(10);}return future.get(100,TimeUnit.MILLISECONDS);}
  private static void check(JSONArray rows,String name,boolean pass)throws Exception{rows.put(new JSONObject().put("name",name).put("pass",pass));if(!pass)throw new IllegalStateException(name);}
  public static void run(File root){JSONObject result=new JSONObject();JSONArray rows=new JSONArray();try{
    result.put("mode","DEVICE_LOCAL_FAKE_EXCHANGE_NO_USB");result.put("hardware_commands",false);
    ControlBroker broker=new ControlBroker();Fake fake=new Fake();String session=call(broker,fake,"start",new JSONObject()).getString("session");check(rows,"start creates unique lease",fake.active&&broker.publicState().getBoolean("active"));
    call(broker,fake,"set",new JSONObject().put("session",session).put("yaw",20).put("pitch",-15));check(rows,"two axis pulse conversion",fake.yaw==1600&&fake.pitch==1425);
    boolean rejected=false;try{call(broker,fake,"heartbeat",new JSONObject().put("session","wrong"));}catch(Exception e){rejected=true;}check(rows,"wrong lease cannot cancel owner",rejected&&fake.active);
    call(broker,fake,"center",new JSONObject().put("session",session));check(rows,"center reply",fake.yaw==1500&&fake.pitch==1500);
    SystemClock.sleep(1850);broker.pump(fake);check(rows,"expired heartbeat stops fake MCU",!fake.active&&!broker.publicState().getBoolean("active"));
    FutureTask<JSONObject> stale=new FutureTask<>(()->broker.submit("start",new JSONObject()));new Thread(stale).start();SystemClock.sleep(40);FutureTask<JSONObject> stop=new FutureTask<>(()->broker.submit("stop",new JSONObject()));new Thread(stop).start();SystemClock.sleep(40);broker.pump(fake);check(rows,"stop rejects queued start",!fake.active&&stop.get(100,TimeUnit.MILLISECONDS).getBoolean("stopped"));try{stale.get(100,TimeUnit.MILLISECONDS);throw new IllegalStateException("stale start survived");}catch(ExecutionException expected){}
    boolean bad=false;try{broker.submit("set",new JSONObject().put("yaw",101).put("pitch",0));}catch(IllegalArgumentException expected){bad=true;}check(rows,"range validation",bad);
    HeadlessSurface surface=new HeadlessSurface(320,240);check(rows,"actual phone offscreen EGL surface",surface.texture()!=null);surface.close();result.put("passed",true);
  }catch(Throwable error){try{result.put("passed",false).put("error",error.toString());}catch(Exception ignored){}}
  try{result.put("checks",rows);try(FileOutputStream out=new FileOutputStream(new File(root,"control-self-check.json"))){out.write(result.toString().getBytes("UTF-8"));out.getFD().sync();}}catch(Exception ignored){}
  }
}
