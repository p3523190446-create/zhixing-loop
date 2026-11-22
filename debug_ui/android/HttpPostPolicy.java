package cn.zhixing.dashboard;

/** Old WebView beacon compatibility; never relax the same-origin check. */
public final class HttpPostPolicy {
  private HttpPostPolicy(){}
  public static boolean allowed(String api,String host,String origin,String contentType){
    if(host==null||!("http://"+host).equals(origin)||contentType==null)return false;
    String type=contentType.split(";",2)[0].trim().toLowerCase(java.util.Locale.US);
    if(type.equals("application/json"))return true;
    return type.equals("text/plain")&&(api.equals("drive/stop")||api.equals("gimbal/stop")||api.equals("gimbal-follow/stop")||api.equals("line-task/stop")||api.equals("record/stop"));
  }
}
