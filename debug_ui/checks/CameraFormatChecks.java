package cn.zhixing.dashboard;

import java.nio.file.Files;
import java.nio.file.Paths;
import org.json.*;

public final class CameraFormatChecks {
  private static int checks;
  private static void check(boolean value){checks++;if(!value)throw new AssertionError("check "+checks);}
  public static void main(String[] args)throws Exception {
    String actual=new String(Files.readAllBytes(Paths.get(args[0])),"UTF-8");
    boolean originalThrows=false;
    try{
      JSONArray formats=new JSONObject(actual).getJSONArray("formats");
      for(int n=0;n<formats.length();n++){
        JSONObject f=formats.getJSONObject(n);
        if(f.optInt("subType")==4)f.getJSONObject("detail");
      }
    }catch(JSONException error){originalThrows=error.getMessage().contains("detail");}
    check(originalThrows);
    CameraFormatInfo.Raw actualInfo=CameraFormatInfo.inspect(actual);
    check(actualInfo.seen);check(!actualInfo.usable());check(actualInfo.names.isEmpty());
    check(new JSONObject(actual).getJSONArray("formats").getJSONObject(0).getInt("subType")==6);
    CameraFormatInfo.Raw mjpeg=CameraFormatInfo.inspect("{\"formats\":[{\"subType\":6}]}");
    check(!mjpeg.seen);check(!mjpeg.usable());
    CameraFormatInfo.Raw yuy2=CameraFormatInfo.inspect("{\"formats\":[{\"subType\":4,\"detail\":{\"GUID\":\"5955593200001000800000AA00389B71\"}}]}");
    check(yuy2.usable());check(yuy2.names.get(0).equals("YUY2"));
    CameraFormatInfo.Raw uyvy=CameraFormatInfo.inspect("{\"formats\":[{\"subType\":4,\"GUID\":\"5559565900001000800000aa00389b71\"}]}");
    check(uyvy.usable());check(uyvy.names.get(0).equals("UYVY"));
    check(!CameraFormatInfo.inspect("{\"formats\":[{\"subType\":4}]}").usable());
    check(!CameraFormatInfo.inspect("{\"formats\":[{\"subType\":4,\"detail\":{}}]}").usable());
    check(!CameraFormatInfo.inspect("{\"formats\":[{\"subType\":4,\"detail\":\"not-an-object\"}]}").usable());
    check(!CameraFormatInfo.inspect("{\"formats\":[{\"subType\":4,\"GUID\":\"4e563132\"}]}").usable());
    check(!CameraFormatInfo.inspect("{\"formats\":[{\"subType\":4,\"GUID\":\"55595659\"},{\"subType\":4}]}").usable());
    System.out.println("PASS "+checks+" checks on real Android org.json; old detail exception reproduced, actual MJPEG-containing format JSON accepted without guessing raw formats; no USB capture acceptance claimed");
  }
}
