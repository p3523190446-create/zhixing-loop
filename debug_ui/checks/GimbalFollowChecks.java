package cn.zhixing.dashboard;
import org.json.*;
import android.os.SystemClock;
import static cn.zhixing.dashboard.GimbalCalibrationChecks.*;

/** Production controller and broker; fake MCU only, never opens USB. */
public final class GimbalFollowChecks {
 static int checks;
 static void ok(boolean value,String why){checks++;System.out.println("FOLLOW "+checks+" "+why);if(!value)throw new AssertionError(why);}
 static GimbalFollower.Frame frame(long seq,long now,double x,double y){return new GimbalFollower.Frame(seq,now,1,8,"TRACKING","red",x,y);}
 static GimbalFollower fresh(){GimbalFollower f=new GimbalFollower();f.start(frame(1,1000,1,1),1000,true,1,-1,true,1645,1920,1000,2000,1000,2000);return f;}
 static void math(){
  GimbalFollower f=fresh();ok(f.yaw()==1645&&f.pitch()==1920,"handoff retains current pose");
  ok(f.yawMin()==1000&&f.yawMax()==2000&&f.pitchMax()==2000,"tracking uses full saved profile");
  f.update(frame(2,1100,1,1),1100,true);ok(f.yaw()==1705&&f.pitch()==1860,"both axes and reverse sign bounded to 60us/100ms");
  int y=f.yaw();f.update(frame(2,1100,1,1),1150,true);ok(f.yaw()==y,"same frame cannot integrate twice");
  for(int i=0;i<10;i++)f.update(frame(3+i,1200+i*20,0,0),1200+i*20,true);y=f.yaw();
  f.update(frame(13,1400,0,0),1400,true);ok(f.yaw()==y&&f.centered(),"filtered center and hysteresis prevent jitter");
  f=fresh();f.start(frame(1,1000,1,1),1000,true,-1,1,false,1645,1920,1000,2000,1000,2000);f.update(frame(2,1100,1,1),1100,true);ok(f.yaw()==1585&&f.pitch()==1920,"horizontal only and inverse sign");
  f=fresh();for(int i=1;i<=100;i++){long t=1000+100*i;f.heartbeat(t);f.update(frame(i+1,t,1,-1),t,true);}ok(f.yaw()==2000&&f.pitch()==2000,"sustained input cannot leave bounded window");
  f=fresh();ok(!f.update(frame(2,1000,1,1),1250,true),"250ms frame expires");
  f=fresh();ok(!f.update(frame(2,1101,1,1),1100,true),"future timestamp rejected");
  f=fresh();ok(!f.update(frame(0,1100,1,1),1100,true),"sequence rollback revokes");
  f=fresh();ok(!f.update(new GimbalFollower.Frame(2,1100,2,8,"TRACKING","red",1.,1.),1100,true),"configuration change revokes");
  f=fresh();ok(f.update(new GimbalFollower.Frame(2,1100,1,9,"TRACKING","red",1.,1.),1100,true)&&f.holding()&&f.yaw()==1645,"stable selected color can renew target identity without a jump");
  f=fresh();ok(f.update(new GimbalFollower.Frame(2,1100,1,8,"LOST","red",null,null),1100,true)&&f.holding(),"fresh missed detection holds instead of revoking");
  f=fresh();ok(!f.update(new GimbalFollower.Frame(2,1100,1,8,"TRACKING","blue",1.,1.),1100,true),"mode change revokes");
  f=fresh();ok(!f.update(frame(2,1100,1,1),1100,false),"vehicle state change revokes");
  f=fresh();ok(!f.update(frame(2,2500,1,1),2500,true),"1500ms enable lease expires");
  boolean bad=false;try{f.heartbeat(2501);}catch(Exception expected){bad=true;}ok(bad&&!f.active(),"late heartbeat cannot resurrect");
  ok(!f.update(frame(3,2502,1,1),2502,true),"fresh target never automatically rearms");
  f=fresh();ok(!f.update(frame(2,1100,Double.NaN,1),1100,true),"nonfinite error rejected");
  f=fresh();f.update(frame(2,1050,1,1),1050,true);ok(!f.update(frame(3,1049,1,1),1100,true),"frame time rollback revokes");
 }
 static final class Source implements GimbalFollower.Source{
  long seq=1;boolean stationary=true,locked=true,stale;long id=8;double x=1;
  public GimbalFollower.Frame latest(){long now=SystemClock.elapsedRealtime();return new GimbalFollower.Frame(seq++,stale?now-250:now,1,id,locked?"TRACKING":"LOST","red",x,1.);}
  public boolean stationary(){return stationary;}
 }
 static JSONObject startBody(String owner)throws Exception{return new JSONObject().put("manual_session",owner).put("confirmed",true).put("yaw_sign",1).put("pitch_sign",-1).put("both_axes",false);}
 static JSONObject token(String s)throws Exception{return new JSONObject().put("session",s);}
 static void broker()throws Exception{
  ControlBroker b=new ControlBroker();MCU m=new MCU();Source source=new Source();b.followSource(source);
  String manual=request(b,m,"start",new JSONObject()).getString("session");int starts=m.starts,pose=m.yaw;source.x=0;
  final String initialManual=manual;
  JSONObject bad=startBody(manual).put("confirmed",false);rejects(()->request(b,m,"follow-start",bad),"confirmation required");ok(m.active&&m.yaw==pose&&m.starts==starts,"invalid handoff preserves manual owner and pose");
  JSONObject wrap=startBody(manual).put("yaw_sign",4294967297L);rejects(()->request(b,m,"follow-start",wrap),"wrapped sign rejected");
  source.stationary=false;rejects(()->request(b,m,"follow-start",startBody(initialManual)),"moving vehicle rejected");source.stationary=true;
  source.stale=true;rejects(()->request(b,m,"follow-start",startBody(initialManual)),"stale source rejected");source.stale=false;
  String auto=request(b,m,"follow-start",startBody(manual)).getString("session");
  ok(m.starts==starts&&m.yaw==pose&&m.pitch==1500,"handoff neither restarts nor recenters MCU");source.x=1;
  rejects(()->request(b,m,"set",token(initialManual).put("yaw",100).put("pitch",0)),"old manual token revoked");
  int movementBegan=m.yaw;long began=SystemClock.elapsedRealtime(),until=began+650,next=0;
  while(SystemClock.elapsedRealtime()<until){long now=SystemClock.elapsedRealtime();if(now>=next){request(b,m,"follow-heartbeat",token(auto));next=now+250;}b.pump(m);Thread.sleep(10);}
  double elapsed=(SystemClock.elapsedRealtime()-began)/1000.;
  ok(m.yaw>movementBegan&&m.yaw-movementBegan<=Math.ceil(elapsed*600)+2&&m.pitch==1500,"broker movement respects rate and horizontal-only setting");
  source.locked=false;int held=m.yaw;b.pump(m);ok(m.active&&m.yaw==held&&b.followState().getString("state").equals("HOLDING"),"single missed detection holds actual output");
  source.locked=true;b.pump(m);ok(m.active&&m.starts==starts,"same identity resumes without MCU restart");
  source.locked=false;long lostAt=SystemClock.elapsedRealtime(),nextBeat=lostAt;
  while(b.following()&&SystemClock.elapsedRealtime()-lostAt<1200){long now=SystemClock.elapsedRealtime();if(now>=nextBeat){request(b,m,"follow-heartbeat",token(auto));nextBeat=now+250;}b.pump(m);Thread.sleep(10);}
  ok(m.active&&b.followState().getString("state").equals("HOLDING"),"sustained color loss holds while camera and operator lease remain live");
  request(b,m,"follow-stop",token(auto));ok(!m.active&&m.yaw==0&&m.pitch==0&&b.followState().getBoolean("stop_confirmed"),"explicit stop from hold reaches acknowledged zero output");
  source.locked=true;b.pump(m);ok(!m.active&&m.starts==starts,"target return does not rearm");
  final String firstAuto=auto;rejects(()->request(b,m,"follow-heartbeat",token(firstAuto)),"revoked automatic token rejected");
  manual=request(b,m,"start",new JSONObject()).getString("session");auto=request(b,m,"follow-start",startBody(manual)).getString("session");
  String manual2=request(b,m,"start",new JSONObject()).getString("session");ok(m.active&&!b.following(),"explicit manual takeover");
  final String old=auto;rejects(()->request(b,m,"follow-stop",token(old)),"old page stop cannot revoke new manual owner");ok(m.active,"manual owner survives obsolete follow stop");
  auto=request(b,m,"follow-start",startBody(manual2)).getString("session");Thread.sleep(1520);b.pump(m);ok(!m.active&&b.followState().getBoolean("stop_confirmed"),"browser lease loss stops MCU");
  manual=request(b,m,"start",new JSONObject()).getString("session");auto=request(b,m,"follow-start",startBody(manual)).getString("session");source.stationary=false;b.pump(m);ok(!m.active,"vehicle interlock revokes active follow");source.stationary=true;
  manual=request(b,m,"start",new JSONObject()).getString("session");auto=request(b,m,"follow-start",startBody(manual)).getString("session");source.stale=true;b.pump(m);ok(!m.active,"stale frame stops active follow");source.stale=false;
  manual=request(b,m,"start",new JSONObject()).getString("session");auto=request(b,m,"follow-start",startBody(manual)).getString("session");b.disconnect();ok(!b.following()&&!b.followState().getBoolean("stop_confirmed"),"disconnect never claims acknowledged physical stop");
 }
 static void responsiveManual()throws Exception{
  ControlBroker b=new ControlBroker();MCU m=new MCU();b.persistence(null,json->{});
  String owner=request(b,m,"start",new JSONObject()).getString("session");
  request(b,m,"set",token(owner).put("yaw",100).put("pitch",100));
  runFor(b,m,owner,650);ok(m.yaw==2000&&m.pitch==2000,"1000us/s reaches full manual corner within 650ms");
  request(b,m,"set",token(owner).put("yaw",-100).put("pitch",-100));runFor(b,m,owner,400);
  ok(m.yaw<=1650&&m.pitch<=1650,"new opposite target replaces old target promptly");
  request(b,m,"stop",new JSONObject());ok(!m.active&&m.yaw==0&&m.pitch==0,"fast manual stop still acknowledged");
  b.configure(new JSONObject().put("rate",2000));owner=request(b,m,"start",new JSONObject()).getString("session");
  request(b,m,"set",token(owner).put("yaw",100).put("pitch",100));runFor(b,m,owner,400);
  ok(m.yaw==2000&&m.pitch==2000,"optional 2000us/s reaches full corner within 400ms");
  request(b,m,"stop",new JSONObject());
 }
 static void extendedManual()throws Exception{
  ControlBroker b=new ControlBroker();MCU m=new MCU();b.persistence(null,json->{});
  b.configure(new JSONObject().put("yaw_min",500).put("yaw_max",2500).put("pitch_min",500).put("pitch_max",2500).put("rate",4000));
  rejects(()->request(b,m,"start",new JSONObject()),"old firmware cannot arm extended bounds");ok(m.starts==0,"capability rejection never arms MCU");
  b.wideCapability(true);String owner=request(b,m,"start",new JSONObject()).getString("session");
  request(b,m,"set",token(owner).put("yaw",100).put("pitch",-100));runFor(b,m,owner,350);
  ok(m.yaw==2500&&m.pitch==500,"expanded endpoints and negative-pitch lift command");
  request(b,m,"set",token(owner).put("yaw",-100).put("pitch",100));runFor(b,m,owner,600);
  ok(m.yaw==500&&m.pitch==2500,"positive pitch lowers; full expanded reversal");
  request(b,m,"stop",new JSONObject());owner=request(b,m,"start",new JSONObject()).getString("session");
  ok(m.active,"manual stop retains verified firmware capability");request(b,m,"stop",new JSONObject());
 }
 public static void main(String[] args){try{math();responsiveManual();extendedManual();broker();System.out.println(new JSONObject().put("follow_checks",checks).put("broker_rejections",GimbalCalibrationChecks.checks).put("fake_mcu",true).put("actual_android_runtime",true).put("physical_motion_tested",false));}catch(Throwable e){e.printStackTrace(System.out);System.exit(1);}}
}
