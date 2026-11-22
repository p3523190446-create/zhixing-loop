package cn.zhixing.dashboard;
public final class HttpPostPolicyChecks {
  private static int checks;
  private static void check(boolean value){checks++;if(!value)throw new AssertionError("check "+checks);}
  public static void main(String[] args){
    String host="127.0.0.1:8780",origin="http://"+host;
    for(String api:new String[]{"drive/stop","gimbal/stop","gimbal-follow/stop","line-task/stop","record/stop"}){
      check(HttpPostPolicy.allowed(api,host,origin,"text/plain;charset=UTF-8"));
      check(HttpPostPolicy.allowed(api,host,origin,"application/json"));
      check(!HttpPostPolicy.allowed(api,host,"http://other.invalid","text/plain"));
      check(!HttpPostPolicy.allowed(api,host,null,"text/plain"));
    }
    for(String api:new String[]{"drive/start","drive/set","gimbal/start","gimbal-follow/start","line-task/start","vision/config","vlm/analyze","gimbal/stop/extra"}){
      check(!HttpPostPolicy.allowed(api,host,origin,"text/plain"));
      check(HttpPostPolicy.allowed(api,host,origin,"application/json; charset=utf-8"));
    }
    check(!HttpPostPolicy.allowed("drive/stop",host,origin,"application/json-evil"));
    check(!HttpPostPolicy.allowed("drive/stop",host,origin,"text/html"));
    check(!HttpPostPolicy.allowed("drive/stop",null,origin,"text/plain"));
    System.out.println("HttpPostPolicy checks: "+checks+" PASS");
  }
}
