package cn.zhixing.carconsole;
import org.json.*;
import java.util.*;
/** Converts existing firmware replies to the existing web UI contract. */
public final class WebState {
    private static long[] row(Map<String,String> m,String key){try{String[] f=m.get(key).split(",",-1);long[] a=new long[f.length-1];for(int k=1;k<f.length;k++)a[k-1]=Long.parseLong(f[k]);return a;}catch(Exception e){return null;}}
    public static JSONObject decode(Map<String,String> m,boolean fresh,long age,long captured)throws Exception{
        JSONObject o=new JSONObject();long[] s=row(m,"STATUS"),u=row(m,"ULTRA_STATUS"),g=row(m,"GIMBAL_STATUS"),p=row(m,"PARAM_STATUS"),r=row(m,"RECOVERY_STATUS"),b=row(m,"MUTE_STATUS"),d=row(m,"MOTOR_DASH_STATUS");
        boolean valid=fresh&&s!=null&&r!=null&&s[2]==0&&s[3]==0&&r[0]==0&&r[4]==0&&r[5]!=3;
        o.put("connected",fresh);o.put("age_ms",fresh?age:JSONObject.NULL);o.put("link_age_ms",fresh?age:JSONObject.NULL);o.put("received_at",captured);
        o.put("range_valid",valid);o.put("distance_mm",valid?s[4]:JSONObject.NULL);o.put("uptime_s",fresh&&s!=null?s[0]/1000:JSONObject.NULL);
        o.put("guard_state",fresh&&r!=null?r[5]:JSONObject.NULL);o.put("warning_mm",fresh&&p!=null?p[0]:JSONObject.NULL);o.put("muted",fresh&&b!=null?b[0]==1:JSONObject.NULL);
        o.put("voltage_mv",fresh&&d!=null&&d[2]==1?d[1]:JSONObject.NULL);o.put("driver_state",fresh&&d!=null?d[10]:JSONObject.NULL);o.put("motor_fault",fresh&&d!=null?d[11]:JSONObject.NULL);o.put("motion_active",fresh&&d!=null&&d[9]!=0);
        JSONArray wheels=new JSONArray();if(fresh&&d!=null&&d[4]==1)for(int k=5;k<9;k++)wheels.put(d[k]);o.put("wheel_speeds_mm_s",wheels.length()==4?wheels:JSONObject.NULL);
        o.put("uart_errors",JSONObject.NULL);o.put("uart_drops",JSONObject.NULL);o.put("mode","PHONE_NATIVE_USBFS_READ_ONLY");
        if(fresh&&u!=null){JSONObject v=new JSONObject();v.put("valid",u[1]==1&&u[2]==1);v.put("distance_mm",u[3]);v.put("age_ms",u[10]+age);o.put("ultrasonic",v);}else o.put("ultrasonic",JSONObject.NULL);
        if(fresh&&g!=null){JSONObject v=new JSONObject();v.put("ready",g[1]==1);v.put("active",g[2]==1);v.put("yaw_us",g[4]);v.put("pitch_us",g[5]);o.put("gimbal",v);}else o.put("gimbal",JSONObject.NULL);
        JSONObject controls=new JSONObject();controls.put("active",false);controls.put("supported",false);o.put("control",controls);o.put("error",fresh?JSONObject.NULL:"等待P7主控连接与新鲜数据");
        return o;
    }
}
