package cn.zhixing.dashboard;
import android.os.SystemClock;
import org.json.*;
import java.util.*;
import java.util.concurrent.*;

/** One expiring owner; calibration uses confirmed, settled command pulses. */
public final class ControlBroker {
 public interface Exchange {String call(String command,String prefix)throws Exception;}
 public interface Store {void save(String json)throws Exception;}
 private static final class Job implements Comparable<Job>{String action;JSONObject body,result;long deadline,sequence;int code=200;CountDownLatch done=new CountDownLatch(1);public int compareTo(Job j){int a=action.equals("stop")||action.equals("follow-stop")?0:1,b=j.action.equals("stop")||j.action.equals("follow-stop")?0:1;return a!=b?a-b:Long.compare(sequence,j.sequence);}}
 private final PriorityBlockingQueue<Job> queue=new PriorityBlockingQueue<>();
 private String owner;private long touch,sequence,starts=-1,lastRamp;
 private int yaw,pitch,wantedYaw=1500,wantedPitch=1500,sentYaw=1500,sentPitch=1500;
 private double budget;private GimbalSettings profile=new GimbalSettings();private Store store;
 private final GimbalFollower follower=new GimbalFollower();private GimbalFollower.Source followSource;
 private boolean automatic,followStopConfirmed,wideCapable;private long lastFollowKeepalive;
 public synchronized void wideCapability(boolean value){wideCapable=value;}
 public synchronized void followSource(GimbalFollower.Source value){followSource=value;if(automatic)follower.stop("视觉输入已改变");}
 public synchronized boolean following(){return automatic;}
 public synchronized JSONObject followState()throws JSONException{GimbalFollower.Frame frame=followSource==null?null:followSource.latest();long now=SystemClock.elapsedRealtime();return new JSONObject().put("active",automatic&&follower.active()).put("state",automatic?(follower.holding()?"HOLDING":follower.centered()?"CENTERED":"TRACKING"):"STOPPED")
   .put("target_locked",GimbalFollower.fresh(frame,now)).put("target_mode",frame==null?JSONObject.NULL:frame.mode)
   .put("source_frame_seq",frame==null?JSONObject.NULL:frame.sequence).put("source_age_ms",frame==null?-1:now-frame.receivedAt)
   .put("manual_ready",owner!=null&&!automatic&&sentYaw==wantedYaw&&sentPitch==wantedPitch)
   .put("message",follower.reason()).put("stop_confirmed",followStopConfirmed).put("mode",follower.mode())
   .put("source_expires_ms",GimbalFollower.FRAME_TTL_MS).put("lease_ms",GimbalFollower.LEASE_MS)
   .put("reacquire_ms",GimbalFollower.REACQUIRE_MS).put("center_dead_zone",GimbalFollower.DEAD_ZONE)
   .put("loss_behavior","HOLD_UNTIL_COLOR_RELOCK")
   .put("error_x",automatic?follower.errorX():JSONObject.NULL).put("error_y",automatic?follower.errorY():JSONObject.NULL)
   .put("target_yaw_us",automatic?follower.yaw():JSONObject.NULL).put("target_pitch_us",automatic?follower.pitch():JSONObject.NULL)
   .put("max_tracking_rate_us_s",GimbalFollower.MAX_RATE_US).put("yaw_min",follower.yawMin()).put("yaw_max",follower.yawMax())
   .put("pitch_min",follower.pitchMin()).put("pitch_max",follower.pitchMax()).put("actuation_enabled",automatic&&follower.active());}
 private final JSONArray events=new JSONArray();
 public synchronized void persistence(String json,Store persistence)throws Exception{if(json!=null)profile=new GimbalSettings().update(new JSONObject(json));store=persistence;}
 public synchronized JSONObject settings()throws JSONException{return profile.publicState().put("extended_firmware",wideCapable);}
 private void save(GimbalSettings next)throws Exception{if(store==null)throw new IllegalStateException("云台参数存储未就绪");store.save(next.values().toString());profile=next;}
 public synchronized JSONObject configure(JSONObject body)throws Exception{if(owner!=null)throw new IllegalStateException("请先停止云台，再保存速度或范围");save(profile.update(body));return settings().put("ok",true);}
 public synchronized JSONObject publicState()throws JSONException{return new JSONObject().put("active",owner!=null).put("state",owner==null?"STOPPED":automatic?"AUTO_TRACKING":"MANUAL").put("target",new JSONObject().put("yaw",yaw).put("pitch",pitch)).put("calibration",settings()).put("events",events);}
 public JSONObject submit(String action,JSONObject body)throws Exception{
  if(!Arrays.asList("start","stop","set","center","heartbeat","calibrate","follow-start","follow-heartbeat","follow-stop").contains(action))throw new IllegalArgumentException("没有这个云台操作");
  if(action.equals("set"))for(String key:new String[]{"yaw","pitch"}){Object n=body.opt(key);if(!(n instanceof Integer||n instanceof Long)||((Number)n).longValue()<-100||((Number)n).longValue()>100)throw new IllegalArgumentException("云台位置越界");}
  if(action.equals("calibrate")&&!Arrays.asList("center","yaw_min","yaw_max","pitch_min","pitch_max").contains(body.optString("point")))throw new IllegalArgumentException("未知校准点");
  if(queue.size()>16&&!action.equals("stop")&&!action.equals("follow-stop"))throw new IllegalStateException("请求队列忙");Job j=new Job();j.action=action;j.body=body;j.deadline=SystemClock.elapsedRealtime()+(action.equals("follow-start")?250:action.equals("follow-heartbeat")?400:2000);synchronized(this){j.sequence=++sequence;}queue.offer(j);
  if(!j.done.await(2600,TimeUnit.MILLISECONDS))throw new IllegalStateException("主控回执超时，控制不会自动恢复");if(j.code!=200)throw new IllegalStateException(j.result.optString("error"));return j.result;
 }
 private long[] gimbal(Exchange x)throws Exception{String[] f=x.call("GIMBAL_STATUS","GIMBAL,").split(",");if(f.length!=11)throw new IllegalStateException("云台回执格式错误");long[] g=new long[10];for(int i=1;i<f.length;i++)g[i-1]=Long.parseLong(f[i]);return g;}
 private void confirmed(Exchange x,String command,String answer)throws Exception{if(!answer.equals(x.call(command,answer)))throw new IllegalStateException("主控回执不符："+command);}
 private void stopped(Exchange x)throws Exception{confirmed(x,"GIMBAL_STOP","GIMBAL_STOPPED");long[] g=gimbal(x);if(g[2]!=0||g[4]!=0||g[5]!=0)throw new IllegalStateException("主控未确认停止");if(automatic){follower.stop(follower.active()?"已停止跟随":follower.reason());followStopConfirmed=true;}automatic=false;owner=null;starts=-1;budget=0;}
 private int sign(JSONObject body,String key)throws JSONException{Object v=body.opt(key);if(!(v instanceof Integer||v instanceof Long)||(((Number)v).longValue()!=1&&((Number)v).longValue()!=-1))throw new IllegalArgumentException("跟随方向格式错误");return ((Number)v).intValue();}
 private void beginFollow(Exchange x,JSONObject body)throws Exception{
  if(owner==null||automatic||!owner.equals(body.optString("manual_session")))throw new IllegalStateException("请先在本页手动对准目标，再交给自动跟随");
  Iterator<String> keys=body.keys();while(keys.hasNext())if(!Arrays.asList("manual_session","confirmed","yaw_sign","pitch_sign","both_axes").contains(keys.next()))throw new IllegalArgumentException("跟随参数格式错误");
  if(!Boolean.TRUE.equals(body.opt("confirmed"))||!(body.opt("both_axes") instanceof Boolean))throw new IllegalArgumentException("请确认车已停稳、云台方向和活动范围");
  if(followSource==null)throw new IllegalStateException("手机视觉源未就绪");
  long[] g=gimbal(x);verify(g);
  if(sentYaw!=wantedYaw||sentPitch!=wantedPitch||Math.abs(g[4]-sentYaw)>2||Math.abs(g[5]-sentPitch)>2)throw new IllegalStateException("云台仍在移动，请停稳再交接");
  follower.start(followSource.latest(),SystemClock.elapsedRealtime(),followSource.stationary(),sign(body,"yaw_sign"),sign(body,"pitch_sign"),body.getBoolean("both_axes"),sentYaw,sentPitch,profile.yawMin,profile.yawMax,profile.pitchMin,profile.pitchMax);
  owner=UUID.randomUUID().toString();automatic=true;followStopConfirmed=false;lastFollowKeepalive=0;wantedYaw=sentYaw;wantedPitch=sentPitch;budget=0;touch=lastRamp=SystemClock.elapsedRealtime();
 }
 private void pumpFollow(Exchange x,long now)throws Exception{
  if(!automatic)return;
  try{
   GimbalFollower.Frame frame=followSource==null?null:followSource.latest();
   boolean stationary=followSource!=null&&followSource.stationary();
   if(!follower.update(frame,SystemClock.elapsedRealtime(),stationary)){stopped(x);return;}
   if(follower.holding())follower.holdAt(sentYaw,sentPitch);
   wantedYaw=follower.yaw();wantedPitch=follower.pitch();yaw=profile.yawValue(wantedYaw);pitch=profile.pitchValue(wantedPitch);
   if(now-lastFollowKeepalive>=300){confirmed(x,"GIMBAL_KEEPALIVE","GIMBAL_ALIVE");verify(gimbal(x));touch=lastFollowKeepalive=SystemClock.elapsedRealtime();}
  }catch(Exception error){follower.stop("控制回执异常，跟随已撤销");try{stopped(x);}catch(Exception unconfirmed){followStopConfirmed=false;}disconnect();throw error;}
 }
 private void verify(long[] g){if(g[1]!=1||g[2]!=1||g[3]!=5||g[6]!=starts)throw new IllegalStateException("主控停止或重启，需要重新开启");}
 private static int toward(int p,int target,int step){return p<target?Math.min(p+step,target):Math.max(p-step,target);}
 private void ramp(Exchange x,long now)throws Exception{
  long dt=Math.max(0,Math.min(250,now-lastRamp));lastRamp=now;if(sentYaw==wantedYaw&&sentPitch==wantedPitch){budget=0;return;}
  budget+=dt*(automatic?Math.min(profile.rate,GimbalFollower.MAX_RATE_US):profile.rate)/1000.0;int step=(int)budget;if(step<1)return;budget-=step;int y=toward(sentYaw,wantedYaw,step),p=toward(sentPitch,wantedPitch,step);
  confirmed(x,"GIMBAL_SET,"+y+","+p,"GIMBAL_SET_ACCEPTED");sentYaw=y;sentPitch=p;
 }
 private JSONObject capture(Exchange x,String point)throws Exception{
  long[] g=gimbal(x);verify(g);if(sentYaw!=wantedYaw||sentPitch!=wantedPitch||Math.abs(g[4]-wantedYaw)>2||Math.abs(g[5]-wantedPitch)>2)throw new IllegalStateException("云台还在移动，请停稳后再保存校准点");
  JSONObject change=new JSONObject();if(point.equals("center"))change.put("yaw_center",(int)g[4]).put("pitch_center",(int)g[5]).put("confirm_center",true);else change.put(point,(int)(point.startsWith("yaw")?g[4]:g[5]));
  save(profile.update(change));yaw=profile.yawValue(wantedYaw);pitch=profile.pitchValue(wantedPitch);
  return new JSONObject().put("ok",true).put("calibration",settings()).put("target",new JSONObject().put("yaw",yaw).put("pitch",pitch));
 }
 public synchronized void pump(Exchange x)throws Exception{
  if(owner!=null&&!automatic&&SystemClock.elapsedRealtime()-touch>=1800)stopped(x);
  for(int i=0;i<4;i++){
   Job j=queue.poll();if(j==null)break;boolean issued=false;
   try{
    if(SystemClock.elapsedRealtime()>j.deadline)throw new IllegalStateException("请求已过期");
    if(j.action.equals("stop")){
     if(j.body.has("session")&&(owner==null||!owner.equals(j.body.optString("session"))))throw new IllegalStateException("控制会话已撤销");
     issued=true;stopped(x);disconnect();j.result=new JSONObject().put("ok",true).put("stopped",true);
    }
    else if(j.action.equals("follow-start")){beginFollow(x,j.body);j.result=followState().put("ok",true).put("session",owner);}
    else if(j.action.equals("follow-stop")||j.action.equals("follow-heartbeat")){
     if(!automatic||owner==null||!owner.equals(j.body.optString("session")))throw new IllegalStateException("跟随会话已撤销");
     if(j.action.equals("follow-stop")){issued=true;follower.stop("已手动停止跟随");stopped(x);j.result=followState().put("ok",true).put("stopped",true);}
     else{follower.heartbeat(SystemClock.elapsedRealtime());j.result=followState().put("ok",true);}
    }
    else if(j.action.equals("start")){
     if(!wideCapable&&(profile.yawMin<1000||profile.yawMax>2000||profile.pitchMin<1000||profile.pitchMax>2000))throw new IllegalStateException("当前主控尚未确认扩展云台范围，请连接新版主控");
     if(automatic){issued=true;follower.stop("已切回手动控制");stopped(x);}
     if(owner!=null)throw new IllegalStateException("其他页面已持有控制");long[] g=gimbal(x);if(g[1]!=1||g[2]!=0)throw new IllegalStateException("主控未就绪或正在动作");
     issued=true;confirmed(x,"GIMBAL_MANUAL_START","GIMBAL_MANUAL_STARTED");starts=g[6]+1;long[] active=gimbal(x);verify(active);
     owner=UUID.randomUUID().toString();touch=lastRamp=SystemClock.elapsedRealtime();yaw=pitch=0;budget=0;sentYaw=(int)active[4];sentPitch=(int)active[5];wantedYaw=profile.yaw(0);wantedPitch=profile.pitch(0);j.result=new JSONObject().put("ok",true).put("session",owner).put("calibration",settings());
    }else{
     if(automatic||owner==null||!owner.equals(j.body.optString("session")))throw new IllegalStateException("控制会话已撤销");
     if(j.action.equals("calibrate")){j.result=capture(x,j.body.getString("point"));touch=SystemClock.elapsedRealtime();}
     else{
      if(j.action.equals("set")||j.action.equals("center")){yaw=j.action.equals("center")?0:j.body.getInt("yaw");pitch=j.action.equals("center")?0:j.body.getInt("pitch");wantedYaw=profile.yaw(yaw);wantedPitch=profile.pitch(pitch);}
      issued=true;confirmed(x,"GIMBAL_KEEPALIVE","GIMBAL_ALIVE");touch=SystemClock.elapsedRealtime();verify(gimbal(x));j.result=new JSONObject().put("ok",true);
     }
    }
    if(!j.action.equals("heartbeat")&&!j.action.equals("follow-heartbeat")){if(events.length()>7)events.remove(0);events.put(new JSONObject().put("message","主控已确认："+j.action));}
   }catch(Exception e){j.code=503;j.result=new JSONObject().put("error",e.getMessage());if(issued){try{stopped(x);}catch(Exception ignored){owner=null;starts=-1;}disconnect();}}
   finally{j.done.countDown();}
  }
  pumpFollow(x,SystemClock.elapsedRealtime());
  if(owner!=null){try{ramp(x,SystemClock.elapsedRealtime());}catch(Exception e){try{stopped(x);}catch(Exception ignored){}disconnect();throw e;}}
 }
 public synchronized void disconnect(){if(automatic){follower.stop("主控连接中断，停止回执未确认");followStopConfirmed=false;}automatic=false;owner=null;starts=-1;budget=0;Job j;while((j=queue.poll())!=null){j.code=503;try{j.result=new JSONObject().put("error","主控已断开");}catch(JSONException ignored){}j.done.countDown();}}
}
