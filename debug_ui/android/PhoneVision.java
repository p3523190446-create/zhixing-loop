package cn.zhixing.dashboard;

import org.json.*;
import java.util.Iterator;

/** Phone-local observation only. No serial, network client, actuator or PC model. */
final class PhoneVision {
  private final PhoneColorTracker tracker=new PhoneColorTracker();
  private PhoneColorTracker.Result latest;private long seq;
  synchronized PhoneColorTracker.Result process(byte[] raw,int w,int h,long receivedAt,long now){return tracker.process(raw,w,h,receivedAt,now);}
  synchronized void publish(PhoneColorTracker.Result result,long sequence){if(result.configuration==tracker.configuration()){latest=result;seq=sequence;}}
  synchronized void reset(){tracker.reset();latest=null;seq=0;}
  synchronized GimbalFollower.Frame followFrame(){
    PhoneColorTracker.Result r=latest;if(r==null||r.configuration!=tracker.configuration())return null;
    return new GimbalFollower.Frame(seq,r.receivedAt,r.configuration,r.trackId,r.state,r.mode,r.errorX,r.errorY);
  }
  synchronized JSONObject configure(JSONObject body,long now)throws JSONException{
    Iterator<String> keys=body.keys();while(keys.hasNext()){String key=keys.next();if(!key.equals("mode")&&!key.equals("enabled"))throw new IllegalArgumentException("跟踪设置格式错误");}
    if(body.has("enabled")&&!(body.get("enabled") instanceof Boolean))throw new IllegalArgumentException("跟踪开关需要布尔值");
    tracker.configure(body.optString("mode",tracker.mode()),body.optBoolean("enabled",tracker.enabled()));latest=null;seq=0;return status(now);
  }
  synchronized JSONObject status(long now)throws JSONException{
    PhoneColorTracker.Result r=latest;long age=r==null?-1:now-r.receivedAt;
    boolean valid=r!=null&&r.configuration==tracker.configuration()&&age>=0&&age<250;
    String state=!tracker.enabled()?"PAUSED":!valid?"STALE":r.state;
    JSONObject result=new JSONObject().put("engine","ANDROID_LOCAL_NV21_COLOR").put("mode",tracker.mode()).put("enabled",tracker.enabled())
      .put("valid",valid).put("state",state).put("frame_seq",seq).put("source_age_ms",age).put("expires_ms",250)
      .put("actuation_enabled",false).put("axis_mapping_verified",false).put("pc_dependency",false)
      .put("bbox",JSONObject.NULL).put("error_x",JSONObject.NULL).put("error_y",JSONObject.NULL).put("pointing_request",JSONObject.NULL);
    JSONArray colors=new JSONArray();
    if(valid){
      for(PhoneColorTracker.Candidate c:r.colors)if(c!=null)colors.put(new JSONObject().put("color",c.color).put("bbox",new JSONArray(c.bbox)).put("area_fraction",c.areaFraction));
      result.put("processing_ms",r.processingNs/1000000.).put("track_id",r.trackId).put("consistent_frames",r.consistentFrames).put("width",r.width).put("height",r.height);
      if(r.bbox!=null)result.put("bbox",new JSONArray(r.bbox)).put("error_x",r.errorX).put("error_y",r.errorY);
      if(r.requestX!=null)result.put("pointing_request",new JSONObject().put("image_x",r.requestX).put("image_y",r.requestY));
    }
    return result.put("colors",colors);
  }
}
