package cn.zhixing.dashboard;
import org.json.*;
import java.util.*;
/** Phone-local command calibration; no angle sensor is present. */
public final class GimbalSettings {
 public final int yawMin,yawCenter,yawMax,pitchMin,pitchCenter,pitchMax,rate;
 public final boolean centerSaved;
 public GimbalSettings(){this(1000,1500,2000,1000,1500,2000,4000,false);}
 private GimbalSettings(int a,int b,int c,int d,int e,int f,int r,boolean saved){
  if(a<500||c>2500||a+20>b||b+20>c||d<500||f>2500||d+20>e||e+20>f||a>1500||c<1500||d>1500||f<1500||!(r==30||r==60||r==100||r==300||r==1000||r==2000||r==4000))throw new IllegalArgumentException("范围需在500～2500内，中位两侧各留20并包含1500；速度需为30、60、100、300、1000、2000或4000");
  yawMin=a;yawCenter=b;yawMax=c;pitchMin=d;pitchCenter=e;pitchMax=f;rate=r;centerSaved=saved;
 }
 private int number(JSONObject d,String key,int fallback)throws JSONException{if(!d.has(key))return fallback;Object n=d.get(key);if(!(n instanceof Integer||n instanceof Long)||((Number)n).longValue()<0||((Number)n).longValue()>10000)throw new IllegalArgumentException("参数需为整数："+key);return ((Number)n).intValue();}
 public GimbalSettings update(JSONObject d)throws JSONException{
  Set<String> keys=new HashSet<>(Arrays.asList("yaw_min","yaw_center","yaw_max","pitch_min","pitch_center","pitch_max","rate","confirm_center"));Iterator<String> it=d.keys();while(it.hasNext())if(!keys.contains(it.next()))throw new IllegalArgumentException("未知云台参数");
  boolean saved=centerSaved;if(d.has("confirm_center")){if(!(d.get("confirm_center") instanceof Boolean))throw new IllegalArgumentException("中位确认需为布尔值");saved=d.getBoolean("confirm_center");}
  if((d.has("yaw_center")||d.has("pitch_center"))&&!d.optBoolean("confirm_center",false))saved=false;
  return new GimbalSettings(number(d,"yaw_min",yawMin),number(d,"yaw_center",yawCenter),number(d,"yaw_max",yawMax),number(d,"pitch_min",pitchMin),number(d,"pitch_center",pitchCenter),number(d,"pitch_max",pitchMax),number(d,"rate",rate),saved);
 }
 public JSONObject values()throws JSONException{return new JSONObject().put("yaw_min",yawMin).put("yaw_center",yawCenter).put("yaw_max",yawMax).put("pitch_min",pitchMin).put("pitch_center",pitchCenter).put("pitch_max",pitchMax).put("rate",rate).put("confirm_center",centerSaved);}
 public JSONObject publicState()throws JSONException{return values().put("hard_min",500).put("hard_max",2500).put("angle_feedback",false).put("units","microseconds").put("speed_units","command_microseconds_per_second");}
 public int yaw(int n){return map(n,yawMin,yawCenter,yawMax);}public int pitch(int n){return map(n,pitchMin,pitchCenter,pitchMax);}
 private static int map(int n,int lo,int mid,int hi){if(n< -100||n>100)throw new IllegalArgumentException("云台指令越界");return n<0?mid+(int)Math.round(n*(mid-lo)/100.0):mid+(int)Math.round(n*(hi-mid)/100.0);}
 public int yawValue(int p){return inverse(p,yawMin,yawCenter,yawMax);}public int pitchValue(int p){return inverse(p,pitchMin,pitchCenter,pitchMax);}
 private static int inverse(int p,int lo,int mid,int hi){return Math.max(-100,Math.min(100,(int)Math.round((p-mid)*100.0/(p<mid?mid-lo:hi-mid))));}
}
