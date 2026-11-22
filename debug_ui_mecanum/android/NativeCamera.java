package cn.zhixing.dashboard;
import android.os.SystemClock;
import java.io.*;
import org.json.*;

/** Camera on CH32 USBHS. Only TelemetryService's existing USB worker calls pump. */
public final class NativeCamera {
  public interface Sink{void frame(byte[] bytes,long at);}
  public interface Priority{void pump()throws Exception;}
  private volatile boolean supported,wanted,running;
  private volatile byte[] jpeg;private volatile long seq,lastFrame;
  private volatile String error="主控转发尚未连接";private volatile Sink sink;
  public void sink(Sink s){sink=s;}
  public void reset(boolean capable){supported=capable;wanted=running=false;jpeg=null;seq=lastFrame=0;error=capable?"画面未开启":"主控转发未连接";}
  public boolean available(){return supported;}
  public JSONObject start(String size,int fps)throws Exception{
    if(!supported)throw new IllegalStateException("P7主控转发未连接");
    if(!size.equals("160x120")||fps!=5)throw new IllegalArgumentException("主控转发目前请选择160×120、5帧；实际预览速度另行统计");
    error=null;wanted=true;long until=SystemClock.elapsedRealtime()+4000;
    while(supported&&wanted&&!running&&SystemClock.elapsedRealtime()<until)SystemClock.sleep(10);
    if(!running){wanted=false;throw new IOException(error==null?"等待主控开启相机超时":error);}
    return status();
  }
  public JSONObject stop()throws Exception{
    wanted=false;jpeg=null;lastFrame=0;long until=SystemClock.elapsedRealtime()+4000;
    while(supported&&running&&SystemClock.elapsedRealtime()<until)SystemClock.sleep(10);
    if(running)throw new IOException("主控关闭相机回执未确认");return status();
  }
  public JSONObject status()throws JSONException{long age=lastFrame==0?-1:SystemClock.elapsedRealtime()-lastFrame;return new JSONObject().put("running",wanted||running).put("valid",wanted&&running&&jpeg!=null&&age>=0&&age<2500).put("width",160).put("height",120).put("requested_fps",5).put("negotiated_fps",5).put("seq",seq).put("age_ms",age).put("error",error==null?JSONObject.NULL:error).put("source","CH32 USBHS camera via P7").put("native_available",supported).put("native_only",true);}
  public byte[] frame()throws IOException{byte[] b=jpeg;if(!wanted||!running||b==null||SystemClock.elapsedRealtime()-lastFrame>=2500)throw new IOException("尚无主控转发新鲜画面");return b;}
  public long sequence(){return seq;}
  private String reply(ControlBroker.Exchange x,String command,String prefix)throws Exception{return x.call(command,prefix);}
  private void close(ControlBroker.Exchange x)throws Exception{String answer=reply(x,"CAMERA_STOP","CAMERA_");if(!answer.equals("CAMERA_STOPPED"))throw new IOException("相机停止回执不符");running=false;jpeg=null;lastFrame=0;error="画面已关闭";}
  public void pump(ControlBroker.Exchange x,Priority priority)throws Exception{
    if(!supported)return;
    if(!wanted&&running){close(x);return;}
    if(wanted&&!running){String answer=reply(x,"CAMERA_START","CAMERA_");if(!answer.equals("CAMERA_STARTED")){wanted=false;error="主控相机启动失败："+answer;return;}running=true;error="等待主控第一帧";}
    if(!wanted||!running)return;
    String[] info=reply(x,"CAMERA_INFO","CAMERA_INFO,").split(",",-1);
    if(info.length!=9)throw new IOException("主控相机状态格式错误");
    if(!info[1].equals("1")){wanted=running=false;jpeg=null;error="相机已停止，状态码"+info[8];return;}
    if(!info[2].equals("1"))return;
    long id=Long.parseLong(info[3]);int length=Integer.parseInt(info[4]);
    if(length<4||length>8192)throw new IOException("主控相机帧大小越界");
    ByteArrayOutputStream bytes=new ByteArrayOutputStream(length);int offset=0;
    while(offset<length){
      priority.pump();if(!wanted){close(x);return;}
      String[] chunk=reply(x,"CAMERA_CHUNK,"+id+","+offset,"CAM").split(",",-1);
      if(chunk.length!=4||!chunk[0].equals("CAMDATA")||Long.parseLong(chunk[1])!=id||Integer.parseInt(chunk[2])!=offset)throw new IOException("主控相机分包编号不符");
      String hex=chunk[3];int n=hex.length()/2;
      if(hex.length()%2!=0||n!=Math.min(64,length-offset)||!hex.matches("[0-9A-F]+"))throw new IOException("主控相机分包内容错误");
      for(int k=0;k<n;k++)bytes.write(Integer.parseInt(hex.substring(k*2,k*2+2),16));offset+=n;
    }
    String released=reply(x,"CAMERA_RELEASE,"+id,"CAM");if(!released.equals("CAMRELEASED"))throw new IOException("主控相机帧释放未确认");
    byte[] picture=bytes.toByteArray();if(picture[0]!=(byte)0xff||picture[1]!=(byte)0xd8||picture[length-2]!=(byte)0xff||picture[length-1]!=(byte)0xd9)throw new IOException("主控相机JPEG不完整");
    if(!wanted){close(x);return;}jpeg=picture;lastFrame=SystemClock.elapsedRealtime();seq++;error=null;Sink s=sink;if(s!=null)s.frame(picture,lastFrame);
  }
}
