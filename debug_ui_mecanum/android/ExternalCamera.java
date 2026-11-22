package cn.zhixing.dashboard;
import android.content.pm.PackageManager;
import android.hardware.usb.UsbDevice;
import android.graphics.*;
import android.os.*;
import com.serenegiant.usb.*;
import java.io.*;
import java.util.*;
import java.nio.ByteBuffer;
import org.json.*;

/** USB UVC -> bounded JPEG publication. No internal camera or microphone. */
public final class ExternalCamera {
  public static final class Capture {
    public final byte[] bytes;public final long sequence,receivedAt;public final int width,height;
    Capture(byte[] bytes,long sequence,long receivedAt,int width,int height){this.bytes=bytes;this.sequence=sequence;this.receivedAt=receivedAt;this.width=width;this.height=height;}
  }
  public interface Sink{void onFrame(byte[] jpeg,long receivedAt);}
  private final GatewayService context;private final Sink sink;private final Handler worker;private final HandlerThread thread;
  private USBMonitor monitor;private UVCCamera camera;private HeadlessSurface surface;private android.view.Surface previewSurface;
  private volatile boolean wanted,permission,opening,encoding;private volatile long epoch,seq,lastFrame,lastCapture,permissionUntil,firstFrameUntil,callbackCount,shortFrames;private volatile byte[] jpeg;
  private volatile int width=640,height=480,requestedWidth=640,requestedHeight=480,requestedFps=15,negotiatedFps=0;
  private volatile String error="画面未开启",deviceName,deviceIdentity="",inputFormat="",compatStage="STOPPED",supportedFormats="";
  private volatile JSONArray supportedModes=new JSONArray();
  public ExternalCamera(GatewayService value,Sink target){context=value;sink=target;thread=new HandlerThread("dashboard-camera");thread.start();worker=new Handler(thread.getLooper());
    monitor=new USBMonitor(context,new USBMonitor.OnDeviceConnectListener(){
      public void onAttach(UsbDevice d){}
      public void onDetach(UsbDevice d){if(selected(d))stopWithReason("摄像头USB已断开");}
      public void onDeviceOpen(UsbDevice d,USBMonitor.UsbControlBlock block,boolean isNew){if(selected(d)&&wanted)open(block);}
      public void onDeviceClose(UsbDevice d,USBMonitor.UsbControlBlock block){if(selected(d)&&wanted)stopWithReason("摄像头USB已断开");}
      public void onCancel(UsbDevice d){if(selected(d))stopWithReason("摄像头USB权限未允许");}
      public void onError(UsbDevice d,USBMonitor.USBException e){if(selected(d))stopWithReason("USB打开失败："+e.getMessage());}
    },worker);monitor.register();worker.post(tick);
  }
  private boolean matches(UsbDevice d){return UsbCameraInfo.camera(d);}
  private boolean selected(UsbDevice d){return d!=null&&d.getDeviceName().equals(deviceName);}
  public synchronized JSONObject compatibility()throws JSONException{
    android.hardware.usb.UsbManager usb=(android.hardware.usb.UsbManager)context.getSystemService(android.content.Context.USB_SERVICE);
    JSONArray devices=new JSONArray();int cameras=0;
    for(UsbDevice d:usb.getDeviceList().values()){if(matches(d))cameras++;devices.put(UsbCameraInfo.describe(d,usb));}
    return new JSONObject().put("stage",compatStage).put("system_usb_devices",devices).put("camera_candidates",cameras)
      .put("selected",deviceIdentity).put("supported_modes",supportedModes).put("native_formats",supportedFormats)
      .put("preview_bridge","UVCAndroid 1.0.13 + format-aware RGBX conversion")
      .put("borrowed_phone_acceptance","NOT_VERIFIED");
  }
  public synchronized JSONObject start(String resolution,int fps)throws Exception{
    if(!Arrays.asList("160x120","320x240","640x480","1280x720","1920x1080").contains(resolution)||!Arrays.asList(5,10,15,20,30).contains(fps))throw new IllegalArgumentException("不支持这组画质或帧率");
    String currentSize=requestedWidth+"x"+requestedHeight;
    if(wanted&&currentSize.equals(resolution)&&requestedFps==fps)return status();
    if(wanted)throw new IllegalStateException("摄像头已开启；切换设置前请点关闭画面");
    if(context.checkSelfPermission(android.Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED)throw new IllegalStateException("请在小安卓手机允许相机权限");
    UsbDevice found=null;for(UsbDevice d:monitor.getDeviceList())if(matches(d)){if(found!=null)throw new IllegalStateException("检测到多个目标摄像头");found=d;}
    if(found==null){compatStage="NOT_ENUMERATED";error="手机系统未枚举到USB相机；P7识别不等于相机已识别";throw new IllegalStateException(error);}
    deviceName=found.getDeviceName();deviceIdentity=UsbCameraInfo.identity(found);compatStage="WAITING_PERMISSION";supportedFormats="";supportedModes=new JSONArray();inputFormat="";negotiatedFps=0;
    context.audit("camera_route_selected","ANDROID_DIRECT_UVC; independent of P7 telemetry");
    String[] sizes=resolution.split("x");width=requestedWidth=Integer.parseInt(sizes[0]);height=requestedHeight=Integer.parseInt(sizes[1]);requestedFps=fps;epoch++;jpeg=null;seq=lastFrame=lastCapture=firstFrameUntil=callbackCount=shortFrames=0;wanted=true;permission=true;permissionUntil=SystemClock.elapsedRealtime()+20000;error="等待小安卓手机USB授权";final UsbDevice device=found;worker.post(()->monitor.requestPermission(device));return status();
  }
  private void open(USBMonitor.UsbControlBlock block){if(!wanted||opening)return;permission=false;opening=true;compatStage="OPENING";final long generation=epoch;try{
    UVCCamera candidate=new UVCCamera(new UVCParam(new Size(UVCCamera.UVC_VS_FRAME_MJPEG,width,height,requestedFps,Arrays.asList(requestedFps)),0));camera=candidate;int result=candidate.open(block);if(result!=0)throw new IOException("UVC打开失败："+result);
    supportedFormats=candidate.getSupportedSize();
    if(supportedFormats==null)supportedFormats="";
    if(supportedFormats.length()>131072)throw new IOException("相机格式描述超限");
    boolean rawSeen=false,rawSupported=true;List<String> rawNames=new ArrayList<>();
    JSONArray nativeFormats=new JSONObject(supportedFormats).getJSONArray("formats");
    for(int n=0;n<nativeFormats.length();n++){JSONObject f=nativeFormats.getJSONObject(n);if(f.optInt("subType")==UVCCamera.UVC_VS_FORMAT_UNCOMPRESSED){rawSeen=true;String guid=f.getJSONObject("detail").optString("GUID","").toLowerCase(Locale.US);if(guid.startsWith("59555932"))rawNames.add("YUY2");else if(guid.startsWith("55595659"))rawNames.add("UYVY");else rawSupported=false;}}
    List<CameraModes.Mode> choices=new ArrayList<>();JSONArray advertised=new JSONArray();
    for(Size size:candidate.getSupportedSizeList()){
      CameraModes.Mode m=new CameraModes.Mode(size.type,size.width,size.height,size.fpsList);if(size.type==CameraModes.MJPEG||(size.type==CameraModes.UNCOMPRESSED&&rawSeen&&rawSupported))choices.add(m);
      if(advertised.length()<128)advertised.put(new JSONObject().put("type",size.type).put("width",size.width).put("height",size.height).put("fps",new JSONArray(size.fpsList)));
    }
    supportedModes=advertised;compatStage="READ_MODES";
    CameraModes.Mode chosen=CameraModes.choose(choices,requestedWidth,requestedHeight,requestedFps);
    if(chosen==null)throw new IOException("没有可处理的MJPEG或未压缩视频模式，格式已保留到兼容报告");
    Size mode=new Size(chosen.type,chosen.width,chosen.height,CameraModes.fps(chosen,requestedFps),chosen.fps);
    candidate.setPreviewSize(mode);width=mode.width;height=mode.height;negotiatedFps=mode.fps;
    inputFormat=mode.type==CameraModes.MJPEG?"MJPEG":rawNames.toString();compatStage="MODE_NEGOTIATED";
    context.audit("uvc_compatibility",compatibility().toString());
    surface=new HeadlessSurface(width,height);previewSurface=new android.view.Surface(surface.texture());candidate.setPreviewDisplay(previewSurface);
    candidate.setFrameCallback(new IFrameCallback(){public void onFrame(ByteBuffer frame){long now=SystemClock.elapsedRealtime();if(!wanted||epoch!=generation)return;callbackCount++;if(frame.remaining()<width*height*3/2){shortFrames++;return;}if(encoding||now-lastCapture<1000/requestedFps)return;lastCapture=now;encoding=true;final byte[] raw=new byte[width*height*3/2];frame.duplicate().get(raw);final int w=width,h=height;worker.post(()->{try{if(!wanted||epoch!=generation)return;ByteArrayOutputStream bytes=new ByteArrayOutputStream();if(!new YuvImage(raw,ImageFormat.NV21,w,h,null).compressToJpeg(new Rect(0,0,w,h),75,bytes))throw new IOException("JPEG编码失败");byte[] image=bytes.toByteArray();boolean first;synchronized(ExternalCamera.this){if(!wanted||generation!=epoch)return;first=seq==0;jpeg=image;lastFrame=now;seq++;error=null;compatStage="STREAMING";}if(first)context.audit("uvc_first_jpeg",w+"x"+h+" bytes="+image.length);sink.onFrame(image,now);}catch(Exception e){error=e.toString();context.audit("jpeg_error",error);}finally{encoding=false;}});}},UVCCamera.PIXEL_FORMAT_NV21);
    if(!wanted||generation!=epoch){destroy();return;}candidate.startPreview();firstFrameUntil=SystemClock.elapsedRealtime()+10000;error="等待第一帧";context.audit("uvc_opened",width+"x"+height+" requested="+requestedFps+" negotiated="+negotiatedFps);
  }catch(Throwable e){error="相机取流失败（"+compatStage+"）："+e.toString();compatStage="FAILED";wanted=false;destroy();context.audit("uvc_error",error);}finally{opening=false;}}
  private void destroy(){UVCCamera old=camera;camera=null;if(old!=null)try{old.destroy();}catch(Throwable ignored){}android.view.Surface oldPreview=previewSurface;previewSurface=null;if(oldPreview!=null)oldPreview.release();HeadlessSurface oldSurface=surface;surface=null;if(oldSurface!=null)oldSurface.close();}
  public synchronized JSONObject status()throws JSONException{long age=lastFrame==0?-1:SystemClock.elapsedRealtime()-lastFrame;boolean valid=wanted&&jpeg!=null&&age>=0&&age<2000;String phase=!wanted?"STOPPED":permission?"WAITING_PERMISSION":opening?"OPENING":valid?"STREAMING":"WAITING_FRAME";return new JSONObject().put("running",wanted).put("valid",valid).put("phase",phase).put("width",width).put("height",height).put("requested_fps",requestedFps).put("negotiated_fps",negotiatedFps).put("seq",seq).put("age_ms",age).put("callback_count",callbackCount).put("short_frames",shortFrames).put("error",error==null?JSONObject.NULL:error).put("source","Android external UVC "+deviceIdentity).put("input_format",inputFormat).put("compatibility_stage",compatStage).put("requested_resolution",requestedWidth+"x"+requestedHeight).put("mode_fallback",width!=requestedWidth||height!=requestedHeight).put("camera_usb_present",monitor.getDeviceList().stream().anyMatch(this::matches)).put("native_available",false).put("native_only",false);}
  public synchronized byte[] frame()throws Exception{if(!wanted||jpeg==null||SystemClock.elapsedRealtime()-lastFrame>=2000)throw new IOException("尚无新鲜画面");return jpeg;}
  public synchronized Capture capture()throws Exception{return new Capture(frame(),seq,lastFrame,width,height);}
  public long sequence(){return seq;}
  private synchronized JSONObject stopWithReason(String why){wanted=false;permission=false;epoch++;jpeg=null;lastFrame=firstFrameUntil=0;error=why;compatStage="画面已关闭".equals(why)?"STOPPED":"FAILED";context.audit("camera_stopped",why);worker.post(this::destroy);try{return status();}catch(JSONException e){return new JSONObject();}}
  public synchronized JSONObject stop(){return stopWithReason("画面已关闭");}
  public void close(){stop();worker.removeCallbacks(tick);worker.post(()->{monitor.destroy();thread.quitSafely();});}
  private final Runnable tick=new Runnable(){public void run(){long now=SystemClock.elapsedRealtime();if(permission&&now>permissionUntil)stopWithReason("摄像头授权超时");else if(wanted&&!permission&&!opening&&seq==0&&firstFrameUntil>0&&now>=firstFrameUntil)stopWithReason("未收到第一帧；可关闭后重试，回调="+callbackCount+" 短帧="+shortFrames);worker.postDelayed(this,1000);}};
}
