package cn.zhixing.dashboard;

import android.os.SystemClock;
import org.json.*;
import java.io.IOException;
import java.util.*;

/** Phone owns durable profiles; only the existing USB worker applies and verifies them. */
public final class LineCalibration {
  public interface Store {void save(String json)throws Exception;}
  private final Store store;
  private JSONObject saved;
  private boolean supported,applied,pending;
  private String phase="等待连接主控",surface="";
  private long began,lastAt,lastAnalog=-1,lastDigital=-1,errors,overflows;
  private final ArrayList<int[]> samples=new ArrayList<>();
  private int[] floor,black,floorNoise,blackNoise;
  public LineCalibration(String json,Store store)throws Exception{
    this.store=store;if(json!=null){JSONObject p=new JSONObject(json);validateProfile(p);saved=p;}
  }
  private static int[] array(JSONObject p,String key)throws Exception{
    JSONArray a=p.getJSONArray(key);if(a.length()!=8)throw new IOException("八路参数长度错误");int[] v=new int[8];
    for(int i=0;i<8;i++){Object n=a.get(i);if(!(n instanceof Integer||n instanceof Long)||((Number)n).longValue()<0||((Number)n).longValue()>65535)throw new IOException("八路参数范围错误");v[i]=((Number)n).intValue();}return v;
  }
  public static long fingerprint(int[] floor,int[] black){long h=2166136261L;for(int[] a:new int[][]{floor,black})for(int n:a)for(int shift=0;shift<=8;shift+=8)h=((h^((n>>shift)&255))*16777619L)&0xffffffffL;return h;}
  private static void validateProfile(JSONObject p)throws Exception{
    int[] f=array(p,"floor"),b=array(p,"black");for(int i=0;i<8;i++)if(b[i]-f[i]<300)throw new IOException("黑线与地面反差不足：X"+(i+1));
    if(p.getLong("id")!=fingerprint(f,b))throw new IOException("标定校验不符");
  }
  public synchronized boolean busy(){return !surface.isEmpty()||pending;}
  public synchronized boolean ready(){return supported&&applied&&saved!=null;}
  public synchronized JSONObject state()throws Exception{
    long remaining=surface.isEmpty()?0:Math.max(0,6000-(SystemClock.elapsedRealtime()-began));
    JSONObject s=new JSONObject().put("supported",supported).put("applied",applied).put("saved",saved!=null).put("ready",ready()).put("busy",busy()).put("surface",surface).put("samples",samples.size()).put("remaining_ms",remaining).put("message",phase).put("floor_done",floor!=null).put("black_done",black!=null);
    if(saved!=null)s.put("profile",new JSONObject(saved.toString()));
    if(floor!=null)s.put("floor",new JSONArray(floor));if(black!=null)s.put("black",new JSONArray(black));return s;
  }
  public synchronized void disconnect(){supported=false;applied=false;pending=false;surface="";floor=black=floorNoise=blackNoise=null;samples.clear();phase=saved==null?"等待连接主控":"标定保存在手机，重连主控后自动核对";}
  private static void exact(ControlBroker.Exchange link,String command,String expected)throws Exception{if(!expected.equals(link.call(command,expected)))throw new IOException("标定回执不符");}
  private void apply(ControlBroker.Exchange link,JSONObject p)throws Exception{
    int[] f=array(p,"floor"),b=array(p,"black");StringBuilder cmd=new StringBuilder("LINE_TASK_CAL_SET");for(int[] a:new int[][]{f,b})for(int v:a)cmd.append(',').append(v);
    exact(link,cmd.toString(),"LINE_TASK_CAL_SAVED,"+p.getLong("id"));
    StringBuilder expected=new StringBuilder("LINE_TASK_CAL,").append(p.getLong("id"));for(int[] a:new int[][]{f,b})for(int v:a)expected.append(',').append(v);
    exact(link,"LINE_TASK_CAL_GET",expected.toString());
  }
  public synchronized void connect(ControlBroker.Exchange link)throws Exception{
    disconnect();supported="LINE_TASK_CAL_CAPS,1,8".equals(link.call("LINE_TASK_CAL_CAPS","LINE_TASK_CAL_CAPS,"));
    if(!supported){phase="主控需更新现场标定固件";return;}
    if(saved!=null){try{apply(link,saved);applied=true;phase="已恢复手机标定，并核对主控参数";}catch(Exception e){phase="恢复标定失败："+e.getMessage();throw e;}}
    else phase="首次使用：先采地砖，再采黑胶带";
  }
  public synchronized JSONObject command(String action,boolean idle,JSONObject live)throws Exception{
    if(action.equals("cancel")){surface="";pending=false;samples.clear();phase="本次采样已取消，原标定保留";return state();}
    if(!supported)throw new IOException("主控需更新现场标定固件");if(!idle)throw new IOException("请先停止行驶和云台，再标定");if(busy())throw new IOException("正在采样或保存，请稍候");
    if(action.equals("save")){
      if(floor==null||black==null)throw new IOException("请先完成地砖与黑胶带两次采样");checkPair();pending=true;phase="正在下发并核对主控，随后保存到手机";return state();
    }
    if(!action.equals("floor")&&!action.equals("black"))throw new IllegalArgumentException("没有这个标定操作");
    if(action.equals("black")&&floor==null)throw new IOException("请先采地砖");
    if(!fresh(live))throw new IOException("等待新鲜八路数据；上电后约等20秒");
    if(action.equals("floor")){floor=black=floorNoise=blackNoise=null;}else{black=blackNoise=null;}
    surface=action;samples.clear();began=SystemClock.elapsedRealtime();lastAt=began;JSONObject line=live.getJSONObject("line");lastAnalog=line.getLong("analog_frames");lastDigital=line.getLong("digital_frames");errors=line.optLong("uart_errors");overflows=line.optLong("overflows");phase=action.equals("floor")?"地砖采集中：保持整排探头静止":"黑胶带采集中：保持整排探头静止";return state();
  }
  private static boolean fresh(JSONObject live){JSONObject l=live.optJSONObject("line");return live.optBoolean("connected")&&!live.optBoolean("motion_active")&&l!=null&&l.optBoolean("valid")&&l.optLong("age_ms",99999)>=0&&l.optLong("age_ms",99999)<1500;}
  public synchronized void observe(JSONObject live,boolean idle)throws Exception{
    if(surface.isEmpty())return;long now=SystemClock.elapsedRealtime();
    if(!idle||!fresh(live)){fail("采样中断：主控数据过期或机构未停止，请重新采集");return;}
    JSONObject l=live.getJSONObject("line");long a=l.getLong("analog_frames"),d=l.getLong("digital_frames");
    if(l.optLong("uart_errors")!=errors||l.optLong("overflows")!=overflows||a<lastAnalog||d<lastDigital){fail("采样中断：通信错误或计数回退，请重新采集");return;}
    if(now-began>10000||now-lastAt>2200){fail("采样不足：请保持连接后重新采集");return;}
    if(a==lastAnalog||d==lastDigital)return;
    lastAnalog=a;lastDigital=d;lastAt=now;samples.add(array(l,"raw"));
    if(now-began<6000||samples.size()<6)return;
    int[] median=new int[8],noise=new int[8];for(int i=0;i<8;i++){int[] v=new int[samples.size()];for(int j=0;j<v.length;j++)v[j]=samples.get(j)[i];Arrays.sort(v);median[i]=v[v.length/2];noise[i]=v[v.length-1]-v[0];if(noise[i]>200){fail("X"+(i+1)+"读数波动较大，请保持高度和探头静止后重采");return;}}
    boolean isFloor=surface.equals("floor");surface="";
    if(isFloor){floor=median;floorNoise=noise;phase="地砖已采好；让整排八个探头覆盖黑胶带，再采黑线";}
    else{black=median;blackNoise=noise;try{checkPair();phase="两组数据合格，点击保存并应用";}catch(Exception error){black=blackNoise=null;phase=error.getMessage()+"；请核对整排覆盖和高度后重采";}}
  }
  private void fail(String message){surface="";samples.clear();phase=message;}
  private void checkPair()throws Exception{for(int i=0;i<8;i++){int gap=black[i]-floor[i];if(gap<300)throw new IOException("X"+(i+1)+"黑线与地砖反差不足或采样顺序相反");if(Math.max(floorNoise[i],blackNoise[i])*5>gap)throw new IOException("X"+(i+1)+"读数波动相对反差过大");}}
  /** Called only by the shared serial worker, after stop queues. No motor command. */
  public synchronized void pump(ControlBroker.Exchange link,boolean idle)throws Exception{
    if(!pending)return;pending=false;if(!idle){phase="保存取消：请先停止机构";return;}
    JSONObject p=new JSONObject().put("version",1).put("floor",new JSONArray(floor)).put("black",new JSONArray(black)).put("id",fingerprint(floor,black)).put("saved_wall_ms",System.currentTimeMillis());
    applied=false;try{apply(link,p);store.save(p.toString());saved=p;applied=true;phase="已保存到手机并核对主控；下次连接自动恢复";}catch(Exception error){phase="保存未完成："+error.getMessage()+"；请重新保存";}
  }
}
