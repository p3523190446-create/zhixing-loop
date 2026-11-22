package cn.zhixing.dashboard;

import android.os.SystemClock;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** One motor owner; bounded vectors and expiring jobs, with a separate stop lane. */
public final class DriveBroker {
  private static final class Job {
    String action;JSONObject body,result;long deadline;int code=200;
    final CountDownLatch done=new CountDownLatch(1);
  }
  private final ArrayBlockingQueue<Job> queue=new ArrayBlockingQueue<>(8);
  private final ConcurrentLinkedQueue<Job> stops=new ConcurrentLinkedQueue<>();
  private volatile boolean mecanum;
  public synchronized void setMecanum(boolean enabled){if(owner!=null)throw new IllegalStateException("请先停止行驶");mecanum=enabled;}
  private String owner;private long generation,sequence,lastTouch,armedAtMcuMs;private int left,right;
  private static long integer(JSONObject body,String key,long low,long high){
    Object raw=body.opt(key);
    if(!(raw instanceof Integer||raw instanceof Long)||((Number)raw).longValue()<low||((Number)raw).longValue()>high)
      throw new IllegalArgumentException("四驱参数格式或范围错误："+key);
    return ((Number)raw).longValue();
  }
  public synchronized JSONObject publicState()throws JSONException{
    return new JSONObject().put("active",owner!=null).put("mode","MANUAL_FILMING")
      .put("protocol_version",mecanum?5:2).put("chassis",mecanum?"mecanum":"differential").put("control_model","wheel_speed")
      .put("left_pwm",left).put("right_pwm",right).put("generation",generation)
      .put("last_seq",sequence).put("ground_driving_verified",false);
  }
  /** Physical MCU state may revoke a browser owner; polling never renews motion. */
  public synchronized void observe(String raw)throws Exception{
    if(raw==null)return;String[] parts=raw.split(",",-1);
    if(parts.length!=10||!parts[0].equals("DRIVE"))throw new IllegalStateException("四驱实际状态格式错误");
    // A telemetry cycle can predate a start pumped later in that same cycle.
    long sampleMs=Long.parseLong(parts[1]);
    if(owner!=null&&sampleMs>=armedAtMcuMs&&(Long.parseLong(parts[2])!=1||Long.parseLong(parts[4])!=generation))disconnect();
  }
  public JSONObject submit(String action,JSONObject body)throws Exception{
    if(!Arrays.asList("start","set","stop","brake").contains(action))throw new IllegalArgumentException("没有这个行驶操作");
    if(action.equals("start")&&!"manual".equals(body.optString("mode")))throw new IllegalArgumentException("请刷新页面，使用手动拍摄遥控");
    if(action.equals("brake"))integer(body,"seq",1,2147483647);
    if(action.equals("set")){integer(body,"seq",1,2147483647);integer(body,"throttle",-100,100);integer(body,"turn",-100,100);integer(body,"limit",1,100);if(body.has("strafe"))integer(body,"strafe",-100,100);if(!mecanum&&body.optInt("strafe",0)!=0)throw new IllegalArgumentException("当前固件不支持横移");}
    Job job=new Job();job.action=action;job.body=body;job.deadline=SystemClock.elapsedRealtime()+450;
    if(action.equals("stop")||action.equals("brake")){
      if(stops.size()>=4)throw new IllegalStateException("停止请求已在处理中");
      stops.offer(job);
    }else if(!queue.offer(job))throw new IllegalStateException("行驶请求队列忙");
    if(!job.done.await(1800,TimeUnit.MILLISECONDS))throw new IllegalStateException("四驱回执超时，需重新开启");
    if(job.code!=200)throw new IllegalStateException(job.result.optString("error"));
    return job.result;
  }
  private static String exact(ControlBroker.Exchange link,String request,String response)throws Exception{
    String got=link.call(request,response);if(!got.equals(response))throw new IllegalStateException("四驱回执不符");return got;
  }
  private long[] status(ControlBroker.Exchange link)throws Exception{
    String[] values=link.call("DRIVE_STATUS","DRIVE,").split(",",-1);
    if(values.length!=10)throw new IllegalStateException("四驱状态格式错误");
    long[] result=new long[9];for(int i=1;i<values.length;i++)result[i-1]=Long.parseLong(values[i]);return result;
  }
  private void stop(ControlBroker.Exchange link)throws Exception{
    owner=null;left=right=0;sequence=0;
    exact(link,"DRIVE_STOP","DRIVE_STOPPED");
    long[] state=status(link);
    if(state[1]!=0||state[2]!=0||state[5]!=0||state[6]!=0)throw new IllegalStateException("主控尚未确认零目标");
  }
  private void complete(Job job,int code,JSONObject result){job.code=code;job.result=result;job.done.countDown();}
  private void cancelQueued(String message)throws JSONException{
    Job job;while((job=queue.poll())!=null)complete(job,503,new JSONObject().put("error",message));
  }
  private Exception revokeAfterError(ControlBroker.Exchange link,Exception original){
    Exception fatal=null;
    try{stop(link);}catch(Exception stopError){fatal=stopError;}
    disconnect();
    if(fatal!=null)return fatal;
    return original instanceof java.io.IOException&&!(original instanceof BoardReplyException)?original:null;
  }
  public synchronized void pump(ControlBroker.Exchange link)throws Exception{
    Job emergency=stops.poll();
    if(emergency!=null){
      boolean emergencyIssued=false;
      try{
        if(emergency.action.equals("brake")){
          if(owner==null||!owner.equals(emergency.body.optString("session")))throw new IllegalStateException("四驱会话已撤销");
          long next=integer(emergency.body,"seq",1,2147483647);if(next<=sequence)throw new IllegalStateException("归零序号已过期");
          cancelQueued("松手已撤销较旧请求");
          emergencyIssued=true;exact(link,"DRIVE_BRAKE,"+generation+","+next,"DRIVE_BRAKED");
          sequence=next;left=right=0;lastTouch=SystemClock.elapsedRealtime();
          complete(emergency,200,new JSONObject().put("ok",true).put("braked",true));
        }else{cancelQueued("停止已撤销待执行请求");emergencyIssued=true;stop(link);complete(emergency,200,new JSONObject().put("ok",true).put("stopped",true));}
      }
      catch(Exception error){Exception fatal=emergencyIssued?revokeAfterError(link,error):null;complete(emergency,503,new JSONObject().put("error",error.getMessage()));if(fatal!=null)throw fatal;}
      return;
    }
    if(owner!=null&&SystemClock.elapsedRealtime()-lastTouch>=900){stop(link);cancelQueued("会话已过期，请重新开启");}
    Job job=queue.poll();if(job==null)return;boolean issued=false;
    try{
      if(SystemClock.elapsedRealtime()>job.deadline)throw new IllegalStateException("行驶请求已过期，未执行");
      if(job.action.equals("start")){
        if(owner!=null)throw new IllegalStateException("另一页面已持有四驱控制");
        issued=true;String reply=link.call("DRIVE_ARM","DRIVE_ARMED,");
        String[] parts=reply.split(",",-1);if(parts.length!=2)throw new IllegalStateException("未收到四驱开启回执");
        generation=Long.parseLong(parts[1]);if(generation<=0)throw new IllegalStateException("四驱代次错误");
        long[] state=status(link);if(state[1]!=1||state[2]!=0||state[3]!=generation)throw new IllegalStateException("主控未确认本次零目标开启");
        armedAtMcuMs=state[0];owner=UUID.randomUUID().toString();sequence=0;left=right=0;lastTouch=SystemClock.elapsedRealtime();
        complete(job,200,new JSONObject().put("ok",true).put("session",owner));return;
      }
      if(owner==null||!owner.equals(job.body.optString("session")))throw new IllegalStateException("四驱会话已撤销");
      long next=integer(job.body,"seq",1,2147483647);if(next<=sequence)throw new IllegalStateException("旧行驶序号已拒绝");
      int throttle=(int)integer(job.body,"throttle",-100,100),turn=(int)integer(job.body,"turn",-100,100),limit=(int)integer(job.body,"limit",1,100);
      double l=throttle+turn,r=throttle-turn,scale=Math.max(100,Math.max(Math.abs(l),Math.abs(r)));
      int nextLeft=(int)Math.round(l/scale*250*limit/100),nextRight=(int)Math.round(r/scale*250*limit/100);
      int strafe=job.body.has("strafe")?(int)integer(job.body,"strafe",-100,100):0;
      if(!mecanum&&strafe!=0)throw new IllegalArgumentException("当前固件不支持横移");
      if(mecanum){
        // Scale all axes together BEFORE MCU mixing; respect the selected speed ceiling.
        double norm=Math.max(100,Math.abs(throttle)+Math.abs(strafe)+Math.abs(turn));
        int f=(int)(throttle/norm*250*limit/100),x=(int)(strafe/norm*250*limit/100),z=(int)(turn/norm*250*limit/100);
        issued=true;exact(link,"DRIVE_VECTOR,"+generation+","+next+","+f+","+x+","+z,"DRIVE_VECTOR_ACCEPTED");
        nextLeft=f+x+z;nextRight=f-x-z;
      }else{issued=true;exact(link,"DRIVE_SET,"+generation+","+next+","+nextLeft+","+nextRight,"DRIVE_SET_ACCEPTED");}
      sequence=next;left=nextLeft;right=nextRight;lastTouch=SystemClock.elapsedRealtime();
      complete(job,200,new JSONObject().put("ok",true).put("seq",sequence).put("left_pwm",left).put("right_pwm",right));
    }catch(Exception error){
      Exception fatal=issued?revokeAfterError(link,error):null;
      complete(job,503,new JSONObject().put("error",error.getMessage()==null?error.toString():error.getMessage()));
      if(fatal!=null)throw fatal;
    }
  }
  public synchronized void disconnect(){
    owner=null;generation=sequence=armedAtMcuMs=0;left=right=0;Job job;
    try{cancelQueued("四驱链路已关闭");while((job=stops.poll())!=null)complete(job,503,new JSONObject().put("error","四驱链路已关闭"));}
    catch(JSONException ignored){}
  }
}
