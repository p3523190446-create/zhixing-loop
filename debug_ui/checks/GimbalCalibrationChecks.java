package cn.zhixing.dashboard;
import org.json.*;
import android.os.SystemClock;
import java.util.*;

/** Production broker with a fake MCU, in a separate Android app_process. */
public final class GimbalCalibrationChecks {
 static int checks;static void check(boolean b,String why){checks++;System.out.println("CHECK "+checks+" "+why);if(!b)throw new AssertionError(why);}
 static void rejects(RunnableEx work,String why)throws Exception{boolean bad=false;try{work.run();}catch(Exception expected){bad=true;}check(bad,why);}
 interface RunnableEx {void run()throws Exception;}
 static class MCU implements ControlBroker.Exchange {
  int yaw,pitch,starts,stops;boolean active;List<String> commands=new ArrayList<>();
  public String call(String cmd,String prefix){commands.add(cmd);
   if(cmd.equals("GIMBAL_STATUS"))return "GIMBAL,"+SystemClock.elapsedRealtime()+",1,"+(active?1:0)+",5,"+yaw+","+pitch+","+starts+","+stops+",1000000,1000000";
   if(cmd.equals("GIMBAL_MANUAL_START")){active=true;yaw=pitch=1500;starts++;return "GIMBAL_MANUAL_STARTED";}
   if(cmd.equals("GIMBAL_STOP")){active=false;yaw=pitch=0;stops++;return "GIMBAL_STOPPED";}
   if(cmd.equals("GIMBAL_KEEPALIVE"))return "GIMBAL_ALIVE";
   if(cmd.startsWith("GIMBAL_SET,")){String[] f=cmd.split(",");yaw=Integer.parseInt(f[1]);pitch=Integer.parseInt(f[2]);return "GIMBAL_SET_ACCEPTED";}
   throw new AssertionError("Unexpected command "+cmd);
  }
 }
 static JSONObject request(ControlBroker b,MCU m,String action,JSONObject body)throws Exception{
  final JSONObject[] answer={null};final Exception[] error={null};Thread t=new Thread(()->{try{answer[0]=b.submit(action,body);}catch(Exception e){error[0]=e;}});t.start();
  long until=SystemClock.elapsedRealtime()+2900;while(t.isAlive()&&SystemClock.elapsedRealtime()<until){b.pump(m);Thread.sleep(4);}t.join(20);if(t.isAlive())throw new AssertionError("Broker did not complete");if(error[0]!=null)throw error[0];return answer[0];
 }
 static void runFor(ControlBroker b,MCU m,String owner,int ms)throws Exception{
  long until=SystemClock.elapsedRealtime()+ms,next=0;while(SystemClock.elapsedRealtime()<until){long now=SystemClock.elapsedRealtime();if(now>=next){request(b,m,"heartbeat",new JSONObject().put("session",owner));next=now+250;}b.pump(m);Thread.sleep(10);}
 }
 public static void main(String[] args){try{checks();}catch(Throwable error){error.printStackTrace(System.out);System.exit(1);}}
 public static void checks()throws Exception{
  GimbalSettings s=new GimbalSettings();check(s.yaw(-100)==1000&&s.yaw(100)==2000,"full original range");check(s.rate==4000&&!s.centerSaved,"default responsive uncalibrated");
  s=s.update(new JSONObject().put("yaw_center",1435).put("pitch_center",1510).put("confirm_center",true));check(s.yaw(0)==1435&&s.pitch(0)==1510,"asymmetric middle");check(s.yawValue(1435)==0&&s.pitchValue(1510)==0,"inverse middle");check(s.yaw(-100)==1000&&s.yaw(100)==2000,"independent halves");
  final GimbalSettings fixed=s;
  rejects(()->fixed.update(new JSONObject().put("yaw_min",499)),"lower hard guard");rejects(()->fixed.update(new JSONObject().put("pitch_max",2501)),"upper guard");rejects(()->fixed.update(new JSONObject().put("yaw_min",1490)),"invalid ordering");rejects(()->fixed.update(new JSONObject().put("rate",9999)),"invalid speed");rejects(()->fixed.update(new JSONObject().put("yaw_center",1435.0)),"float rejected");rejects(()->fixed.update(new JSONObject().put("command","RUN")),"unknown key rejected");
  ControlBroker b=new ControlBroker();MCU m=new MCU();final String[] saved={null};b.persistence(null,json->saved[0]=json);
  b.configure(new JSONObject().put("rate",30));check(new JSONObject(saved[0]).getInt("rate")==30,"persisted speed");
  String owner=request(b,m,"start",new JSONObject()).getString("session");check(m.active,"start acknowledged");
  request(b,m,"set",new JSONObject().put("session",owner).put("yaw",100).put("pitch",0));long began=SystemClock.elapsedRealtime();runFor(b,m,owner,900);double elapsed=(SystemClock.elapsedRealtime()-began)/1000.0;
  int travelled=m.yaw-1500;check(travelled>10&&travelled<=Math.ceil(elapsed*30)+3,"30us/s ramp bounded");
  rejects(()->request(b,m,"calibrate",new JSONObject().put("session",owner).put("point","center")),"reject moving calibration");check(m.active,"rejected calibration does not revoke owner");rejects(()->b.configure(new JSONObject().put("rate",100)),"reject config while active");
  request(b,m,"center",new JSONObject().put("session",owner));runFor(b,m,owner,1500);check(m.yaw==1500,"return center settles");
  request(b,m,"calibrate",new JSONObject().put("session",owner).put("point","center"));check(b.settings().getBoolean("confirm_center"),"settled center capture");
  rejects(()->request(b,m,"calibrate",new JSONObject().put("session",owner).put("point","yaw_min")),"reject collapsed boundary");
  request(b,m,"stop",new JSONObject());check(!m.active&&m.yaw==0&&m.pitch==0,"stop confirms zero");
  int writes=m.commands.size();b.configure(new JSONObject().put("yaw_center",1435).put("pitch_center",1510).put("confirm_center",true).put("rate",100));check(m.commands.size()==writes,"configuration does not move");
  ControlBroker restored=new ControlBroker();restored.persistence(saved[0],json->{});check(restored.settings().getInt("yaw_center")==1435,"profile survives restart");
  String owner2=request(b,m,"start",new JSONObject()).getString("session");runFor(b,m,owner2,1200);check(m.yaw==1435&&m.pitch==1510,"start transitions to saved center");
  request(b,m,"set",new JSONObject().put("session",owner2).put("yaw",20).put("pitch",0));runFor(b,m,owner2,1500);check(m.yaw==1548,"calibrated asymmetric map");
  request(b,m,"calibrate",new JSONObject().put("session",owner2).put("point","yaw_max"));check(b.settings().getInt("yaw_max")==1548,"one boundary capture");check(b.settings().getInt("pitch_max")==2000,"other axis unchanged");
  request(b,m,"stop",new JSONObject());rejects(()->request(b,m,"set",new JSONObject().put("session",owner2).put("yaw",100).put("pitch",100)),"old session rejected");
  int startCount=m.starts;b.pump(m);check(m.starts==startCount&&!m.active,"no automatic restart");
  String owner3=request(b,m,"start",new JSONObject()).getString("session");Thread.sleep(1850);b.pump(m);check(!m.active&&m.yaw==0&&m.pitch==0,"lease stops pending ramp");
  b.persistence(null,json->{throw new java.io.IOException("fake storage failure");});int oldRate=b.settings().getInt("rate");rejects(()->b.configure(new JSONObject().put("rate",30)),"storage failure reported");check(b.settings().getInt("rate")==oldRate,"failed storage not published");
  System.out.println(new JSONObject().put("checks",checks).put("fake_mcu",true).put("actual_android_runtime",true).put("rate_test_travel_us",travelled).put("rate_test_seconds",elapsed).put("physical_motion_tested",false).toString());
 }
}
