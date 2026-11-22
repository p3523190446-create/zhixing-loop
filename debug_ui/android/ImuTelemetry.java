package cn.zhixing.dashboard;

import java.util.Map;
import org.json.*;

/** Read-only MCU observer decoder. Never enables sensor compatibility or motion. */
public final class ImuTelemetry {
  // Same saved reference as the deployed r1_imu_observer; a new reference must update this tag.
  public static final long REFERENCE_CRC=2529589088L;
  private static final String[] METRICS={"front_up_deg","left_up_deg","turn_window_deg","yaw_rate_dps","vibration_rms","vibration_peak","jerk"};
  private static final String[] STATES={"ready","low_dynamic","tilt","extreme_tilt","shock_recent","rotating","window_ready","saturated","frozen","freefall","accelerating"};
  private static long[] fields(Map<String,String> rows,String key,int size){
    try{String[] s=rows.get(key).split(",",-1);if(s.length!=size+1||!s[0].equals(key))return null;
      long[] v=new long[size];for(int i=0;i<size;i++)v[i]=Long.parseLong(s[i+1]);return v;
    }catch(Exception error){return null;}
  }
  private static boolean bit(long n){return n==0||n==1;}
  private static boolean uint(long n){return n>=0&&n<=4294967295L;}
  public static JSONObject decode(Map<String,String> rows,long hostAge,boolean connected)throws JSONException{
    JSONObject p=new JSONObject().put("valid",false).put("source_valid",false).put("supported",rows.containsKey("MPU_CAPABLE")?"1".equals(rows.get("MPU_CAPABLE")):JSONObject.NULL)
      .put("age_ms",JSONObject.NULL).put("address",JSONObject.NULL).put("identity",JSONObject.NULL).put("nonstandard_identity",false)
      .put("reference_matches",false).put("front_up_deg",JSONObject.NULL).put("left_up_deg",JSONObject.NULL).put("gyro_delta_raw",JSONObject.NULL)
      .put("features",JSONObject.NULL).put("last_error",JSONObject.NULL).put("note","相对已保存的水平参考；非标准身份兼容测试，精度待核。");
    if(rows.containsKey("MPU_QUERY_ERROR"))p.put("query_error",rows.get("MPU_QUERY_ERROR"));
    long[] s=fields(rows,"MPU_STATUS",11),r=fields(rows,"MPU_RAW",9),f=fields(rows,"MPU_FEATURES",17),h=fields(rows,"MPU_HOST_AGE",1);
    if(s==null||r==null)return p;
    if(!uint(s[0])||!uint(s[10])||!uint(r[0])||!bit(s[1])||!bit(s[2])||!bit(s[5])||!bit(s[6])||!bit(r[1]))return p;
    if(s[3]<0||s[3]>127||s[4]<0||s[4]>255||!uint(s[7])||!uint(s[8])||s[9]<0||s[9]>255)return p;
    for(int i=2;i<9;i++)if(r[i]<-32768||r[i]>32767)return p;
    long extra=Math.max(0,hostAge)+(h==null?0:Math.max(0,h[0]));
    long sensorAge=Math.max(s[10],r[0])+extra;
    boolean reference=s[3]==105&&s[4]==114;
    boolean source=connected&&hostAge>=0&&s[1]==1&&s[2]==1&&r[1]==1&&Math.max(s[10],r[0])<250&&sensorAge<1500&&reference;
    p.put("source_valid",source).put("age_ms",sensorAge).put("address",s[3]).put("identity",s[4]).put("nonstandard_identity",s[4]!=104)
      .put("reference_matches",reference).put("frames",s[7]).put("errors",s[8]).put("last_error",s[9]);
    if(f==null)return p;
    if(!uint(f[0])||!uint(f[1])||!bit(f[2])||f[3]<0||f[3]>=2048)return p;
    for(int i=4;i<=10;i++)if(f[i]<-100000000L||f[i]>100000000L||(i>=8&&f[i]<0))return p;
    for(int i=11;i<17;i++)if(!uint(f[i]))return p;
    boolean matches=f[16]==REFERENCE_CRC,valid=source&&f[2]==1&&(f[3]&1)!=0&&(f[3]&(128|256))==0&&f[1]<250&&f[1]+extra<1500&&matches;
    JSONObject features=new JSONObject().put("supported",true).put("valid",valid).put("age_ms",f[1]+extra).put("reference_matches",matches)
      .put("reference_crc32",f[16]).put("flags",f[3]).put("shock_count",f[11]).put("tilt_count",f[12]).put("freefall_count",f[13])
      .put("window_ms",f[14]).put("frames",f[15]).put("unit","relative_to_saved_gravity").put("sample_hz",20);
    JSONArray states=new JSONArray();if(valid)for(int i=0;i<STATES.length;i++)if((f[3]&(1L<<i))!=0)states.put(STATES[i]);features.put("states",states);
    for(int i=0;i<METRICS.length;i++)features.put(METRICS[i],valid&&(i<4||(f[3]&64)!=0||i==6)?f[4+i]/1000.0:JSONObject.NULL);
    p.put("valid",valid).put("features",features).put("reference_matches",reference&&matches).put("age_ms",Math.max(sensorAge,f[1]+extra));
    if(valid)p.put("front_up_deg",features.get("front_up_deg")).put("left_up_deg",features.get("left_up_deg")).put("attitude_source","mcu_complementary");
    return p;
  }
}
