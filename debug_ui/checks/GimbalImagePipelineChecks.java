package cn.zhixing.dashboard;
import org.json.*;
import android.os.SystemClock;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;
import static cn.zhixing.dashboard.GimbalCalibrationChecks.*;
/** Synthetic NV21 -> production tracker -> follower/broker -> fake MCU. */
public final class GimbalImagePipelineChecks{
 static int checks;
 static void ok(boolean b){checks++;if(!b)throw new AssertionError("pipeline "+checks);}
 static final class Source implements GimbalFollower.Source{
  final PhoneVision vision=new PhoneVision();final int x,y;long seq;boolean lost;
  Source(int x,int y){this.x=x;this.y=y;}
  public GimbalFollower.Frame latest(){
   int w=160,h=120;byte[] a=new byte[w*h*3/2];Arrays.fill(a,0,w*h,(byte)16);Arrays.fill(a,w*h,a.length,(byte)128);
   if(!lost)for(int py=y;py<y+24;py++)for(int px=x;px<x+24;px++){
    a[py*w+px]=(byte)82;int uv=w*h+(py/2)*w+(px/2)*2;a[uv]=(byte)240;a[uv+1]=(byte)90;
   }
   long at=SystemClock.elapsedRealtime();vision.publish(vision.process(a,w,h,at,at),++seq);return vision.followFrame();
  }
  public boolean stationary(){return true;}
 }
 public static void main(String[] args)throws Exception{
  Map<String,String> rows=new HashMap<>();rows.put("DRIVE_STATUS","DRIVE,1000,0,0,23,22,0,0,5,999");
  rows.put("DRIVE_ACTUATORS","ACTUATORS,1000,0,0,0,0,0,0,0,0,0");
  ok(FollowInterlock.blocked(rows,true,0,false,false,false)==null);
  ok(FollowInterlock.blocked(rows,true,0,false,false,true).contains("四驱停止"));
  ok(FollowInterlock.blocked(rows,true,0,false,true,false).contains("循迹"));
  ok(FollowInterlock.blocked(rows,true,1500,false,false,false)!=null);
  ok(FollowInterlock.blocked(rows,false,0,false,false,false)!=null);
  ok(FollowInterlock.blocked(rows,true,0,true,false,false)!=null);
  rows.put("DRIVE_STATUS","DRIVE,1000,0,1,23,22,0,0,5,999");ok(FollowInterlock.blocked(rows,true,0,false,false,false)!=null);
  rows.put("DRIVE_STATUS","DRIVE,1000,0,0,23,22,0,0,5,999");
  rows.put("DRIVE_ACTUATORS","ACTUATORS,1000,0,0,0,0,0,0,0,1,0");ok(FollowInterlock.blocked(rows,true,0,false,false,false)!=null);
  rows.put("DRIVE_ACTUATORS","ACTUATORS,1000,0,0,0,0,0,0,0,0,1");ok(FollowInterlock.blocked(rows,true,0,false,false,false)!=null);
  rows.put("DRIVE_ACTUATORS","broken");ok(FollowInterlock.blocked(rows,true,0,false,false,false)!=null);
  ControlBroker owned=new ControlBroker();MCU ownMcu=new MCU();
  String first=request(owned,ownMcu,"start",new JSONObject()).getString("session");
  request(owned,ownMcu,"stop",new JSONObject().put("session",first));
  request(owned,ownMcu,"start",new JSONObject());boolean refused=false;
  try{request(owned,ownMcu,"stop",new JSONObject().put("session",first));}catch(Exception expected){refused=true;}
  ok(refused&&ownMcu.active);request(owned,ownMcu,"stop",new JSONObject());ok(!ownMcu.active);
  for(int[] pos:new int[][]{{110,80},{30,80},{110,16},{30,16}}){
   Source source=new Source(pos[0],pos[1]);for(int i=0;i<3;i++)source.latest();
   GimbalFollower.Frame f=source.latest();ok("TRACKING".equals(f.state));ok(Math.signum(f.x)==(pos[0]>80?1:-1));ok(Math.signum(f.y)==(pos[1]>60?1:-1));
   ControlBroker b=new ControlBroker();MCU m=new MCU();b.persistence(null,json->{});b.wideCapability(true);b.followSource(source);
   b.configure(new JSONObject().put("yaw_min",500).put("yaw_max",2500).put("pitch_min",500).put("pitch_max",2500)
    .put("yaw_center",1490).put("pitch_center",1480).put("confirm_center",true));
   String manual=request(b,m,"start",new JSONObject()).getString("session");runFor(b,m,manual,100);
   int y=m.yaw,p=m.pitch;
   String auto=request(b,m,"follow-start",new JSONObject().put("manual_session",manual).put("confirmed",true).put("yaw_sign",1).put("pitch_sign",1).put("both_axes",true)).getString("session");
   long until=SystemClock.elapsedRealtime()+180;
   while(SystemClock.elapsedRealtime()<until){b.pump(m);Thread.sleep(8);}
   ok((m.yaw-y)*f.x>0);ok((m.pitch-p)*f.y>0);
   request(b,m,"follow-heartbeat",new JSONObject().put("session",auto));source.lost=true;int held=m.yaw;b.pump(m);ok(m.active&&m.yaw==held);
   long untilLost=SystemClock.elapsedRealtime()+1100,nextBeat=0;
   while(b.following()&&SystemClock.elapsedRealtime()<untilLost){long now=SystemClock.elapsedRealtime();if(now>=nextBeat){request(b,m,"follow-heartbeat",new JSONObject().put("session",auto));nextBeat=now+250;}b.pump(m);Thread.sleep(10);}
   ok(m.active&&b.followState().getString("state").equals("HOLDING"));
   request(b,m,"follow-stop",new JSONObject().put("session",auto));ok(!m.active&&m.yaw==0&&m.pitch==0&&b.followState().getBoolean("stop_confirmed"));
   source.lost=false;for(int i=0;i<3;i++)source.latest();b.pump(m);ok(!m.active&&!b.following());
  }
  System.out.println(new JSONObject().put("checks",checks).put("runtime","JVM").put("synthetic_nv21",true).put("production_tracker_and_broker",true).put("fake_mcu",true).put("actual_motion",false));
 }
}
