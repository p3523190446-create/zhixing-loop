package cn.zhixing.dashboard;
import java.io.*;
import java.util.*;
import org.json.*;
/** Explicit device-local fixture checks. No USB, controls, compatibility or camera access. */
public final class ImuTelemetrySelfCheck {
  private static Map<String,String> good(){Map<String,String> m=new HashMap<>();
    m.put("MPU_CAPABLE","1");m.put("MPU_STATUS","MPU_STATUS,1000,1,1,105,114,1,1,20,0,0,10");
    m.put("MPU_RAW","MPU_RAW,10,1,100,0,17000,100,-1967,12,-128");m.put("MPU_HOST_AGE","MPU_HOST_AGE,5");
    m.put("MPU_FEATURES","MPU_FEATURES,1000,10,1,67,1200,-2300,500,100,2,4,3,0,0,0,2000,20,"+ImuTelemetry.REFERENCE_CRC);return m;}
  private static void check(JSONArray cases,String name,boolean ok)throws Exception{cases.put(new JSONObject().put("name",name).put("pass",ok));if(!ok)throw new IllegalStateException(name);}
  public static void run(File folder){JSONObject report=new JSONObject();JSONArray cases=new JSONArray();try{
    JSONObject p=ImuTelemetry.decode(good(),10,true);check(cases,"live filtered angles and reference",p.getBoolean("valid")&&p.getDouble("front_up_deg")==1.2&&p.getDouble("left_up_deg")==-2.3&&p.getLong("age_ms")==25);
    p=ImuTelemetry.decode(good(),1500,true);check(cases,"host stale clears angle",!p.getBoolean("valid")&&p.isNull("front_up_deg"));
    p=ImuTelemetry.decode(good(),10,false);check(cases,"disconnect clears metrics",!p.getBoolean("valid")&&p.getJSONObject("features").isNull("vibration_rms"));
    Map<String,String> m=good();m.put("MPU_FEATURES",m.get("MPU_FEATURES").replace("2529589088","123"));p=ImuTelemetry.decode(m,10,true);check(cases,"wrong reference rejected",!p.getBoolean("valid")&&!p.getBoolean("reference_matches"));
    m=good();m.put("MPU_STATUS","MPU_STATUS,1000,0,0,105,114,1,1,0,1,4,4294967295");p=ImuTelemetry.decode(m,10,true);check(cases,"compatibility off preserved",!p.getBoolean("valid")&&p.getInt("last_error")==4&&p.getInt("identity")==114);
    m=good();m.put("MPU_RAW","MPU_RAW,10,1,999999,0,17000,100,-1967,12,-128");check(cases,"bad raw rejected",!ImuTelemetry.decode(m,10,true).getBoolean("valid"));
    m=good();m.put("MPU_FEATURES",m.get("MPU_FEATURES").replace(",1,67,",",1,195,"));check(cases,"saturated rejected",!ImuTelemetry.decode(m,10,true).getBoolean("valid"));
    check(cases,"absent sensor still has invalid schema",!ImuTelemetry.decode(new HashMap<>(),-1,false).getBoolean("valid"));
    m=good();m.put("MPU_HOST_AGE","MPU_HOST_AGE,1600");check(cases,"slow sensor batch rejected",!ImuTelemetry.decode(m,0,true).getBoolean("valid"));
    report.put("passed",true);
  }catch(Throwable e){try{report.put("passed",false).put("error",e.toString());}catch(Exception ignored){}}
    try{report.put("checks",cases).put("hardware_commands",false).put("fixtures_only",true);try(FileOutputStream f=new FileOutputStream(new File(folder,"imu-telemetry-self-check.json"))){f.write(report.toString().getBytes("UTF-8"));f.getFD().sync();}}catch(Exception ignored){}
  }
}
