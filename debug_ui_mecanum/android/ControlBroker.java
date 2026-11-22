package cn.zhixing.dashboard;
import android.os.SystemClock;
import org.json.*;
import java.util.*;
import java.util.concurrent.*;

/** Single browser lease. Only fixed gimbal commands, never motor or arbitrary text. */
public final class ControlBroker {
  public interface Exchange {String call(String command,String prefix)throws Exception;}
  private static final class Job implements Comparable<Job>{String action;JSONObject body,result;long deadline,sequence;int code=200;CountDownLatch done=new CountDownLatch(1);public int compareTo(Job j){int a=action.equals("stop")?0:1,b=j.action.equals("stop")?0:1;return a!=b?a-b:Long.compare(sequence,j.sequence);}}
  private final PriorityBlockingQueue<Job> queue=new PriorityBlockingQueue<>();
  private String owner=null;private long touch,sequence,starts=-1;private int yaw,pitch;private final JSONArray events=new JSONArray();
  public synchronized JSONObject publicState()throws JSONException{JSONObject d=new JSONObject();d.put("active",owner!=null);d.put("state",owner==null?"STOPPED":"MANUAL");d.put("target",new JSONObject().put("yaw",yaw).put("pitch",pitch));d.put("events",events);return d;}
  public JSONObject submit(String action,JSONObject body)throws Exception{
    if(!Arrays.asList("start","stop","set","center","heartbeat").contains(action))throw new IllegalArgumentException("没有这个云台操作");
    if(action.equals("set"))for(String key:new String[]{"yaw","pitch"}){Object n=body.opt(key);if(!(n instanceof Integer||n instanceof Long)||((Number)n).longValue()<-100||((Number)n).longValue()>100)throw new IllegalArgumentException("云台位置越界");}
    if(queue.size()>16)throw new IllegalStateException("请求队列忙");
    Job j=new Job();j.action=action;j.body=body;j.deadline=SystemClock.elapsedRealtime()+2000;synchronized(this){j.sequence=++sequence;}queue.offer(j);
    if(!j.done.await(2600,TimeUnit.MILLISECONDS))throw new IllegalStateException("主控回执超时，控制不会自动恢复");
    if(j.code!=200)throw new IllegalStateException(j.result.optString("error"));return j.result;
  }
  private long[] gimbal(Exchange x)throws Exception{String[] f=x.call("GIMBAL_STATUS","GIMBAL,").split(",");if(f.length!=11)throw new IllegalStateException("云台回执格式错误");long[] g=new long[10];for(int i=1;i<f.length;i++)g[i-1]=Long.parseLong(f[i]);return g;}
  private void confirmed(Exchange x,String command,String answer)throws Exception{if(!answer.equals(x.call(command,answer)))throw new IllegalStateException("主控回执不符："+command);}
  private void stopped(Exchange x)throws Exception{confirmed(x,"GIMBAL_STOP","GIMBAL_STOPPED");long[] g=gimbal(x);if(g[2]!=0||g[4]!=0||g[5]!=0)throw new IllegalStateException("主控未确认停止");owner=null;starts=-1;}
  public synchronized void pump(Exchange x)throws Exception{
    if(owner!=null&&SystemClock.elapsedRealtime()-touch>=1800)stopped(x);
    for(int i=0;i<4;i++){
      Job j=queue.poll();if(j==null)break;
      boolean issued=false;
      try{
        if(SystemClock.elapsedRealtime()>j.deadline)throw new IllegalStateException("请求已过期");
        if(j.action.equals("stop")){issued=true;stopped(x);disconnect();j.result=new JSONObject().put("ok",true).put("stopped",true);}
        else if(j.action.equals("start")){
          if(owner!=null)throw new IllegalStateException("其他页面已持有控制");long[] g=gimbal(x);if(g[1]!=1||g[2]!=0)throw new IllegalStateException("主控未就绪或正在动作");
          issued=true;confirmed(x,"GIMBAL_MANUAL_START","GIMBAL_MANUAL_STARTED");starts=g[6]+1;long[] started=gimbal(x);if(started[2]!=1||started[3]!=5||started[6]!=starts)throw new IllegalStateException("主控未确认本次开启");owner=UUID.randomUUID().toString();touch=SystemClock.elapsedRealtime();yaw=pitch=0;j.result=new JSONObject().put("ok",true).put("session",owner);
        }else{
          if(owner==null||!owner.equals(j.body.optString("session")))throw new IllegalStateException("控制会话已撤销");
          issued=true;
          if(j.action.equals("set")||j.action.equals("center")){yaw=j.action.equals("center")?0:j.body.getInt("yaw");pitch=j.action.equals("center")?0:j.body.getInt("pitch");confirmed(x,"GIMBAL_SET,"+(1500+yaw*5)+","+(1500+pitch*5),"GIMBAL_SET_ACCEPTED");}
          confirmed(x,"GIMBAL_KEEPALIVE","GIMBAL_ALIVE");touch=SystemClock.elapsedRealtime();long[] g=gimbal(x);if(g[2]!=1||g[3]!=5||g[6]!=starts)throw new IllegalStateException("主控停止或重启，需要重新开启");j.result=new JSONObject().put("ok",true);
        }
        if(!j.action.equals("heartbeat")){if(events.length()>7)events.remove(0);events.put(new JSONObject().put("message","主控已确认："+j.action));}
      }catch(Exception e){j.code=503;j.result=new JSONObject().put("error",e.getMessage());if(issued){try{stopped(x);}catch(Exception ignored){owner=null;starts=-1;}disconnect();}}
      finally{j.done.countDown();}
    }
  }
  public synchronized void disconnect(){owner=null;starts=-1;Job j;while((j=queue.poll())!=null){j.code=503;try{j.result=new JSONObject().put("error","主控已断开");}catch(JSONException ignored){}j.done.countDown();}}
}
