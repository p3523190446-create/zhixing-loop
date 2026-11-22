package cn.zhixing.dashboard;
import java.io.*;
import java.net.*;
import org.json.JSONObject;

/** Same-origin browser relay to the configured LAN picture service, no actuators. */
public final class LargeVisionProxy {
  private final LargeVisionSettings settings;
  public LargeVisionProxy(LargeVisionSettings value){settings=value;}
  public JSONObject request(String route,JSONObject body)throws Exception{
    if(!route.equals("status")&&!route.equals("analyze")&&!route.matches("job/[0-9]{8}-[0-9]{6}-[a-f0-9]{8}"))
      throw new IllegalArgumentException("没有这个模型接口");
    String base=settings.state().optString("url","");
    if(base.isEmpty())throw new IllegalStateException("请先配置电脑模型服务地址");
    HttpURLConnection connection=(HttpURLConnection)new URL(base+"/api/vlm/"+route).openConnection();
    connection.setConnectTimeout(5000);connection.setReadTimeout(6000);connection.setInstanceFollowRedirects(false);
    try{
      if(body!=null){
        if(!route.equals("analyze"))throw new IllegalArgumentException("模型接口方法错误");
        byte[] bytes=body.toString().getBytes("UTF-8");
        if(bytes.length>3100000)throw new IllegalArgumentException("图片请求过大");
        URI target=new URI(base);connection.setRequestMethod("POST");connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type","application/json");
        connection.setRequestProperty("Origin",target.getScheme()+"://"+target.getRawAuthority());
        connection.setFixedLengthStreamingMode(bytes.length);
        try(OutputStream out=connection.getOutputStream()){out.write(bytes);}
      }
      int code=connection.getResponseCode();
      if(code>=300&&code<400)throw new IOException("模型服务不允许重定向");
      InputStream input=code>=400?connection.getErrorStream():connection.getInputStream();
      if(input==null)throw new IOException("电脑模型服务未返回结果");
      try(InputStream in=input;ByteArrayOutputStream out=new ByteArrayOutputStream()){
        byte[] chunk=new byte[4096];int n;
        while((n=in.read(chunk))>0){out.write(chunk,0,n);if(out.size()>1000000)throw new IOException("模型响应超过限制");}
        JSONObject result=new JSONObject(out.toString("UTF-8"));
        if(code>=400)throw new IOException(result.optString("error","电脑模型服务未确认请求"));
        return result;
      }
    }catch(SocketTimeoutException error){throw new IOException("小手机连接电脑模型服务超时，请检查电脑热点和模型服务");}
    finally{connection.disconnect();}
  }
}
