package cn.zhixing.dashboard;
import java.util.*;
import org.json.*;
/** Serial wire fields -> public UI schema. No device I/O. */
public final class TelemetryCodec {
  private static long[] values(Map<String,String> rows,String key){try{String[] f=rows.get(key).split(",",-1);long[] result=new long[f.length-1];for(int i=1;i<f.length;i++)result[i-1]=Long.parseLong(f[i]);return result;}catch(Exception e){return null;}}
  public static JSONObject decode(Map<String,String> rows,long age,boolean busy,String error)throws JSONException{
    JSONObject out=new JSONObject();boolean fresh=busy&&age>=0&&age<2500;
    out.put("connected",fresh);out.put("age_ms",age<0?JSONObject.NULL:age);out.put("link_age_ms",age<0?JSONObject.NULL:age);
    out.put("error",fresh?JSONObject.NULL:error);out.put("received_at",rows.get("STATUS"));out.put("serial_source","Android P7 USBFS");out.put("motion_active",false);
    for(String key:new String[]{"distance_mm","voltage_mv","uptime_s","warning_mm","wheel_speeds_mm_s","guard_state","muted","driver_state","motor_fault","uart_errors","uart_drops"})out.put(key,JSONObject.NULL);
    out.put("range_valid",false);out.put("gimbal",JSONObject.NULL);out.put("ultrasonic",JSONObject.NULL);out.put("line",JSONObject.NULL);
    if(!fresh)return out;
    long[] s=values(rows,"STATUS"),r=values(rows,"RECOVERY_STATUS"),p=values(rows,"PARAM_STATUS"),m=values(rows,"MUTE_STATUS"),d=values(rows,"MOTOR_DASH_STATUS"),g=values(rows,"GIMBAL_STATUS"),u=values(rows,"ULTRA_STATUS");
    if(s!=null&&s.length==11){boolean valid=s[2]==0&&s[3]==0&&s[4]!=4294967295L&&r!=null&&r[0]==0&&r[4]==0&&r[5]!=3;out.put("range_valid",valid);out.put("distance_mm",valid?s[4]:JSONObject.NULL);out.put("uptime_s",s[0]/1000);}
    if(r!=null)out.put("guard_state",r[5]);if(p!=null)out.put("warning_mm",p[0]);if(m!=null)out.put("muted",m[0]!=0);
    if(d!=null&&d.length==14){out.put("voltage_mv",d[2]==1?d[1]:JSONObject.NULL);out.put("driver_state",d[10]);out.put("motor_fault",d[11]);out.put("motion_active",d[9]!=0);if(d[4]==1){JSONArray wheels=new JSONArray();for(int i=5;i<9;i++)wheels.put(d[i]);out.put("wheel_speeds_mm_s",wheels);}}
    if(g!=null&&g.length==10){JSONObject v=new JSONObject();String[] names={"ms","ready","active","mode","yaw_us","pitch_us","starts","stops","yaw_hz","pitch_hz"};for(int i=0;i<names.length;i++)v.put(names[i],g[i]);out.put("gimbal",v);}
    if(u!=null&&u.length==12){JSONObject v=new JSONObject();boolean valid=u[1]==1&&u[2]==1;v.put("valid",valid);v.put("distance_mm",valid?u[3]:JSONObject.NULL);v.put("status",u[2]);v.put("age_ms",u[10]);out.put("ultrasonic",v);}
    long[] act=values(rows,"DRIVE_ACTUATORS"),drive=values(rows,"DRIVE_STATUS");
    if(act!=null&&act.length==10){JSONArray pwm=new JSONArray(),targets=new JSONArray();for(int i=1;i<=4;i++)pwm.put(act[i]);for(int i=5;i<=8;i++)targets.put(act[i]);out.put("control_model","wheel_speed").put("applied_pwm",pwm).put("speed_targets",targets).put("controller_fault",act[9]);}
    if(drive!=null&&drive.length==9)out.put("motion_active",out.optBoolean("motion_active")||drive[2]!=0);
    long[] la=values(rows,"LINE_ANALOG"),ld=values(rows,"LINE_DIGITAL"),ls=values(rows,"LINE_STATUS");
    if(la!=null&&la.length==10&&ld!=null&&ld.length==3&&ls!=null&&ls.length==12&&ld[2]>=0&&ld[2]<=255){
      JSONArray raw=new JSONArray();boolean range=true;for(int i=2;i<10;i++){raw.put(la[i]);range&=la[i]>=0&&la[i]<=65535;}
      JSONObject v=new JSONObject();v.put("valid",range&&la[1]==1&&ld[1]==1&&ls[10]==1&&ls[11]==1);
      v.put("age_ms",Math.max(la[0],ld[0])+age).put("raw",raw).put("digital_mask",ld[2]);
      v.put("analog_frames",ls[2]).put("digital_frames",ls[3]).put("rejected_frames",ls[4]).put("uart_errors",ls[5]).put("overflows",ls[6]);out.put("line",v);
    }
    return out;
  }
}
