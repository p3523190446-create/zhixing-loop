package cn.zhixing.uvcpreview;
import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.hardware.usb.UsbDevice;
import android.graphics.*;
import android.os.*;
import android.util.Log;
import android.view.*;
import android.widget.*;
import com.serenegiant.usb.*;
import java.io.*;
import java.nio.ByteBuffer;
import java.util.*;
import org.json.*;

public class MainActivity extends Activity implements SurfaceHolder.Callback {
 private USBMonitor monitor;
 private UVCCamera camera;
 private HandlerThread workerThread;
 private Handler worker;
 private final Handler ui=new Handler();
 private SurfaceView view;
 private TextView status;
 private volatile boolean resumed,surfaceReady,opening,streaming,snapshotSaved,permissionRequested;
 private volatile long frames,lastFrameMs,startedMs;
 private volatile String message="等待通过OTG接入外接摄像头";
 private volatile int width=640,height=480,requestedFps=10;
 private volatile int desiredWidth=640,desiredHeight=480;
 private File journal;
 private long lastStatsMs,lastStatsFrames;
 private boolean timeoutSent;

 public void onCreate(Bundle state){
  super.onCreate(state);
  journal=new File(getFilesDir(),"uvc-"+System.currentTimeMillis()+".jsonl");
  event("app_start",android.os.Build.MODEL+" / Android "+android.os.Build.VERSION.RELEASE);
  workerThread=new HandlerThread("UvcPreviewWorker");workerThread.start();worker=new Handler(workerThread.getLooper());
  LinearLayout box=new LinearLayout(this);box.setOrientation(1);box.setPadding(12,12,12,12);
  TextView title=new TextView(this);title.setText("知行回路 · 外接摄像头");title.setTextSize(20);box.addView(title);
  status=new TextView(this);status.setTextSize(15);box.addView(status);
  Spinner resolution=new Spinner(this);
  resolution.setAdapter(new ArrayAdapter<String>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"320×240 · 低负载","640×480 · 默认","1280×720 · 试用","1920×1080 · 试用"}));
  resolution.setSelection(1);box.addView(resolution);
  resolution.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){
   public void onNothingSelected(AdapterView<?> parent){}
   public void onItemSelected(AdapterView<?> parent,View selected,int position,long id){
    final int[] widths={320,640,1280,1920},heights={240,480,720,1080};
    if(desiredWidth==widths[position] && desiredHeight==heights[position])return;
    desiredWidth=widths[position];desiredHeight=heights[position];event("resolution_requested",desiredWidth+"x"+desiredHeight);
    permissionRequested=false;
    worker.post(new Runnable(){public void run(){closeCamera("正在切换分辨率");ui.postDelayed(new Runnable(){public void run(){findCamera();}},300);}});
   }
  });
  LinearLayout buttons=new LinearLayout(this);
  Button start=new Button(this);start.setText("开始预览");buttons.addView(start,new LinearLayout.LayoutParams(0,-2,1));
  Button stop=new Button(this);stop.setText("停止");buttons.addView(stop,new LinearLayout.LayoutParams(0,-2,1));box.addView(buttons);
  start.setOnClickListener(new View.OnClickListener(){public void onClick(View v){permissionRequested=false;findCamera();}});
  stop.setOnClickListener(new View.OnClickListener(){public void onClick(View v){worker.post(new Runnable(){public void run(){closeCamera("用户停止");}});}});
  view=new SurfaceView(this);view.getHolder().addCallback(this);box.addView(view,new LinearLayout.LayoutParams(-1,0,1));
  TextView note=new TextView(this);note.setText("外接USB画面 · 不控制车辆\n取流和错误自动记录；每轮最多预览120秒。");box.addView(note);setContentView(box);
  monitor=new USBMonitor(this,new USBMonitor.OnDeviceConnectListener(){
   public void onAttach(UsbDevice d){if(matches(d)){permissionRequested=false;event("attach","145F:02EC");findCamera();}}
   public void onDetach(UsbDevice d){if(matches(d)){permissionRequested=false;closeCamera("摄像头已拔下");event("detach","145F:02EC");}}
   public void onDeviceOpen(UsbDevice d,USBMonitor.UsbControlBlock c,boolean isNew){if(matches(d))openCamera(c);}
   public void onDeviceClose(UsbDevice d,USBMonitor.UsbControlBlock c){if(matches(d))closeCamera("USB连接已关闭");}
   public void onCancel(UsbDevice d){permissionRequested=false;message="摄像头USB权限未允许";event("usb_permission_cancel","145F:02EC");}
   public void onError(UsbDevice d,USBMonitor.USBException e){message="USB打开失败："+e.getMessage();event("usb_error",e.toString());}
  },worker);
  if(checkSelfPermission(Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.CAMERA},1);
 }
 private boolean matches(UsbDevice d){return d!=null && d.getVendorId()==0x145f && d.getProductId()==0x02ec;}
 private void findCamera(){
  if(!resumed || !surfaceReady || monitor==null || camera!=null || opening)return;
  if(checkSelfPermission(Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED){message="请允许相机权限后点开始预览";return;}
  for(UsbDevice d:monitor.getDeviceList())if(matches(d)){
   if(!permissionRequested){permissionRequested=true;message="已找到外接摄像头，正在申请USB访问权限";event("request_usb_permission","145F:02EC");monitor.requestPermission(d);}return;
  }
  message="等待外接摄像头：手机→OTG→摄像头";
 }
 private void openCamera(USBMonitor.UsbControlBlock block){
  if(!resumed || !surfaceReady || camera!=null || opening)return;
  opening=true;
  try{
   UVCParam param=new UVCParam(new Size(UVCCamera.UVC_VS_FRAME_MJPEG,desiredWidth,desiredHeight,10,Arrays.asList(10)),0);
   UVCCamera candidate=new UVCCamera(param);camera=candidate;
   int result=candidate.open(block);event("uvc_open",String.valueOf(result));
   if(result!=0)throw new IllegalStateException("UVC open="+result);
   List<Size> supported=candidate.getSupportedSizeList();
   event("supported_modes",String.valueOf(supported));
   Size chosen=null;
   for(Size s:supported)if(s.width==desiredWidth && s.height==desiredHeight && s.type==UVCCamera.UVC_VS_FRAME_MJPEG){chosen=s.clone();break;}
   if(chosen==null)throw new IllegalStateException("摄像头未提供所选MJPEG分辨率，请换一个选项");
   int preferred=0;
   for(Integer fps:chosen.fpsList)if(fps>=5 && fps<=10 && fps>preferred)preferred=fps;
   if(preferred==0)throw new IllegalStateException("所选分辨率无5至10帧低负载模式，请选更低分辨率");
   chosen.fps=preferred;candidate.setPreviewSize(chosen);width=chosen.width;height=chosen.height;requestedFps=chosen.fps;
   candidate.setPreviewDisplay(view.getHolder().getSurface());
   frames=0;lastFrameMs=0;snapshotSaved=false;timeoutSent=false;startedMs=SystemClock.elapsedRealtime();lastStatsMs=startedMs;lastStatsFrames=0;
   candidate.setFrameCallback(new IFrameCallback(){public void onFrame(ByteBuffer frame){
    frames++;lastFrameMs=SystemClock.elapsedRealtime();
    if(!snapshotSaved && frames>=8 && frame.remaining()>=width*height*3/2){
     snapshotSaved=true;byte[] bytes=new byte[width*height*3/2];frame.duplicate().get(bytes);
     worker.post(new Runnable(){public void run(){try{
      File target=new File(getFilesDir(),"external-camera.jpg");
      try(FileOutputStream out=new FileOutputStream(target)){if(!new YuvImage(bytes,ImageFormat.NV21,width,height,null).compressToJpeg(new Rect(0,0,width,height),80,out))throw new IOException("JPEG conversion failed");}
      event("snapshot_saved",target.getName());
     }catch(Exception e){event("snapshot_error",e.toString());}}});
    }
   }},UVCCamera.PIXEL_FORMAT_NV21);
   candidate.startPreview();streaming=true;message="正在读取外接摄像头";event("preview_started",chosen.toString());
  }catch(Throwable e){message="取流失败："+e.getClass().getSimpleName()+" "+e.getMessage();event("preview_error",message);closeCamera(message);}
  finally{opening=false;}
 }
 private void closeCamera(String why){
  streaming=false;UVCCamera old=camera;camera=null;
  if(old!=null){try{old.destroy();}catch(Throwable e){event("close_error",e.toString());}}
  message=why;event("preview_stopped",why);
 }
 private synchronized void event(String kind,String detail){
  try{
   JSONObject item=new JSONObject();item.put("event",kind);item.put("elapsed_ms",SystemClock.elapsedRealtime());item.put("frames",frames);item.put("width",width);item.put("height",height);item.put("requested_fps",requestedFps);item.put("detail",detail);
   String row=item.toString();Log.i("ZXR_UVC",row);
   if(journal!=null && journal.length()<1024*1024)try(FileOutputStream f=new FileOutputStream(journal,true)){f.write((row+"\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));}
   try(FileOutputStream f=new FileOutputStream(new File(getFilesDir(),"latest-uvc-status.json"))){f.write(row.getBytes(java.nio.charset.StandardCharsets.UTF_8));}
  }catch(Exception ignored){Log.e("ZXR_UVC","无法保存诊断日志");}
 }
 private final Runnable poll=new Runnable(){public void run(){
  if(!resumed)return;long now=SystemClock.elapsedRealtime();
  String freshness=lastFrameMs==0?"尚未收到视频帧":(now-lastFrameMs>2000?"视频帧已停止更新":"视频帧正在更新");
  status.setText(message+"\n"+width+"×"+height+" · 请求"+requestedFps+"帧/秒\n已收到 "+frames+" 帧 · "+freshness);
  if(streaming && now-lastStatsMs>=1000){
   double actual=(frames-lastStatsFrames)*1000.0/(now-lastStatsMs);event("frame_stats",String.format(Locale.US,"callback_fps=%.2f,age_ms=%d",actual,lastFrameMs==0?-1:now-lastFrameMs));lastStatsMs=now;lastStatsFrames=frames;
   if(lastFrameMs==0 && now-startedMs>8000){timeoutSent=true;worker.post(new Runnable(){public void run(){closeCamera("8秒未收到画面，已停止取流");}});}
  }
  if(streaming && !timeoutSent && now-startedMs>=120000){timeoutSent=true;worker.post(new Runnable(){public void run(){closeCamera("本轮120秒测试已结束");}});}
  ui.postDelayed(this,1000);
 }};
 public void onRequestPermissionsResult(int req,String[] permissions,int[] results){super.onRequestPermissionsResult(req,permissions,results);event("camera_permission",results.length>0 && results[0]==PackageManager.PERMISSION_GRANTED?"granted":"denied");findCamera();}
 public void onResume(){super.onResume();resumed=true;monitor.register();ui.post(poll);findCamera();}
 public void onPause(){resumed=false;ui.removeCallbacks(poll);monitor.unregister();worker.post(new Runnable(){public void run(){closeCamera("页面已退出");}});super.onPause();}
 public void onDestroy(){worker.post(new Runnable(){public void run(){closeCamera("程序退出");monitor.destroy();workerThread.quitSafely();}});super.onDestroy();}
 public void surfaceCreated(SurfaceHolder h){surfaceReady=true;findCamera();}
 public void surfaceChanged(SurfaceHolder h,int format,int w,int height){}
 public void surfaceDestroyed(SurfaceHolder h){surfaceReady=false;worker.post(new Runnable(){public void run(){closeCamera("预览窗口关闭");}});}
}
