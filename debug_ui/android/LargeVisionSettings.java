package cn.zhixing.dashboard;
import android.content.Context;
import android.content.SharedPreferences;
import java.net.URI;
import org.json.JSONObject;

/** Shared camera-model connection for every browser visiting this phone. */
public final class LargeVisionSettings {
  private final SharedPreferences preferences;
  public LargeVisionSettings(Context context){preferences=context.getSharedPreferences("large_vision",0);}
  public synchronized JSONObject state()throws Exception{return new JSONObject().put("url",preferences.getString("url",""))
    .put("deployment","computer_local_ollama").put("actuation_enabled",false);}
  public synchronized JSONObject save(JSONObject body)throws Exception{
    if(body.length()!=1||!body.has("url"))throw new IllegalArgumentException("模型连接参数错误");
    String value=body.getString("url").trim();URI uri;
    try{uri=new URI(value);}catch(Exception error){throw new IllegalArgumentException("请填写电脑模型服务的完整HTTP地址");}
    String host=uri.getHost();boolean local="localhost".equals(host);
    if(host!=null&&host.matches("[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+")){
      String[] fields=host.split("\\.");int[] ip=new int[4];boolean valid=true;
      for(int n=0;n<4;n++){try{ip[n]=Integer.parseInt(fields[n]);}catch(Exception error){valid=false;}if(ip[n]<0||ip[n]>255)valid=false;}
      local=valid&&(ip[0]==127||ip[0]==10||ip[0]==192&&ip[1]==168||ip[0]==172&&ip[1]>=16&&ip[1]<=31);
    }
    if(!"http".equals(uri.getScheme())||!local||uri.getUserInfo()!=null||uri.getQuery()!=null||uri.getFragment()!=null
      ||uri.getPort()<1||uri.getPort()>65535||!uri.getPath().matches("/[A-Za-z0-9_-]{24,64}/?"))
      throw new IllegalArgumentException("请填写本机或局域网电脑模型服务的完整地址，包含端口和路径");
    if(value.endsWith("/"))value=value.substring(0,value.length()-1);
    if(!preferences.edit().putString("url",value).commit())throw new IllegalStateException("模型地址未保存，请重试");
    return state();
  }
}
