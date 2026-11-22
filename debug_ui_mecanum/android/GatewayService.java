package cn.zhixing.dashboard;
import android.app.*;
import android.content.*;
import android.os.*;
import org.json.*;
import java.net.*;
import java.util.*;
import java.io.*;

/** Foreground onboard web host; has no PC address or PC fallback. */
public class GatewayService extends Service {
  public static final int PORT=8780;private volatile int boundPort=PORT;private String token;private LocalHttpServer http;
  private TelemetryService board;private boolean bound;private PowerManager.WakeLock wake;
  private ExternalCamera camera;private VideoRecorder recorder;private PhotoStore photos;private UsbInventoryMonitor usbInventory;
  public class LocalBinder extends Binder{public GatewayService getService(){return GatewayService.this;}}
  private final ServiceConnection binding=new ServiceConnection(){public void onServiceConnected(ComponentName name,IBinder binder){board=((TelemetryService.LocalBinder)binder).getService();board.nativeCamera.sink((bytes,at)->{if(recorder!=null)recorder.frame(bytes,at);});}public void onServiceDisconnected(ComponentName name){board=null;}};
  public IBinder onBind(Intent intent){return new LocalBinder();}
  public void boundPort(int value){boundPort=value;try{JSONObject runtime=new JSONObject().put("port",value).put("base",base()).put("pc_dependency",false);try(FileOutputStream out=new FileOutputStream(new File(getFilesDir(),"web-runtime.json"))){out.write(runtime.toString().getBytes("UTF-8"));out.getFD().sync();}}catch(Exception error){audit("runtime_write_error",error.toString());}}
  public String localAddress(){return "http://127.0.0.1:"+boundPort+"/"+token+"/";}
  public String base(){return "/"+token;}
  public String remoteAddress(){try{Enumeration<NetworkInterface> interfaces=NetworkInterface.getNetworkInterfaces();while(interfaces.hasMoreElements()){NetworkInterface n=interfaces.nextElement();if(!n.getName().equals("wlan0"))continue;Enumeration<InetAddress> addresses=n.getInetAddresses();while(addresses.hasMoreElements()){InetAddress a=addresses.nextElement();if(a instanceof Inet4Address&&!a.isLoopbackAddress())return "http://"+a.getHostAddress()+":"+boundPort+base()+"/mobile";}}}catch(Exception ignored){}return "请连接主力iPhone热点；连接后此处自动显示访问地址";}
  public void onCreate(){super.onCreate();token=getSharedPreferences("web",0).getString("token",null);if(token==null){token=UUID.randomUUID().toString().replace("-","");getSharedPreferences("web",0).edit().putString("token",token).commit();}
    ((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(new NotificationChannel("web","车载调试台",NotificationManager.IMPORTANCE_LOW));
    startForeground(11,new Notification.Builder(this,"web").setSmallIcon(android.R.drawable.stat_notify_sync).setContentTitle("知行回路 · 车载网页服务").setContentText("iPhone可访问本手机，无需电脑").setContentIntent(PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_UPDATE_CURRENT)).setOngoing(true).build());
    wake=((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"zhixing:web-host");wake.acquire();
    bound=bindService(new Intent(this,TelemetryService.class),binding,BIND_AUTO_CREATE);
    recorder=new VideoRecorder(this,()->snapshot());photos=new PhotoStore(this);camera=new ExternalCamera(this,(bytes,at)->recorder.frame(bytes,at));
    http=new LocalHttpServer(this);try{http.start();}catch(Exception error){audit("http_start_failed",error.toString());}
    usbInventory=new UsbInventoryMonitor(this,this::audit);
    audit("gateway_started","onboard Android host");
  }
  public int onStartCommand(Intent i,int flags,int startId){return START_NOT_STICKY;}
  public NativeCamera nativeCamera(){return board!=null&&board.nativeCamera.available()?board.nativeCamera:null;}
  public JSONObject snapshot()throws Exception{TelemetryService current=board;JSONObject data=TelemetryCodec.decode(current==null?Collections.emptyMap():current.snapshot(),current==null?-1:current.sampleAge(),current!=null&&current.isBusy(),current==null?"等待手机主控记录服务":current.phase());data.put("control",current==null?new JSONObject().put("active",false):current.remoteState());data.put("capabilities",new JSONObject().put("gimbal_control",current!=null&&current.gimbalAvailable()).put("gimbal_reason","连接主控并开始记录后可控制；结束记录后需重新开启云台"));data.put("drive",current==null?new JSONObject().put("active",false):current.driveState());
    data.getJSONObject("capabilities").put("drive_control",current!=null&&current.manualDriveAvailable())
      .put("drive_reason","需要手动拍摄固件v3及新鲜主控状态")
      .put("ground_control",current!=null&&current.manualDriveAvailable()).put("range_interlock",current==null||!current.manualDriveAvailable()).put("ground_driving_verified",false).put("motor_pwm_limit",current==null?0:current.drivePwmLimit()).put("driver_pwm_range",3600).put("ground_reason","手动拍摄固件就绪后可落地遥控，测距只提示；地面转向待实测，驱动线断开停车仍未解决");
    data.getJSONObject("capabilities").put("mecanum_control",current!=null&&current.driveMecanum()&&current.manualDriveAvailable());
    if(current!=null&&current.driveNative()){
      data.put("speed_commands",data.opt("applied_pwm")).put("applied_pwm",JSONObject.NULL).put("control_model","driver_native_speed");
      data.getJSONObject("capabilities").put("motor_pwm_limit",JSONObject.NULL).put("driver_native_pid",true).put("driver_speed_limit",current.driveSpeedLimit());
      String profile=current.snapshot().get("DRIVE_PROFILE");
      if(profile!=null){String[] f=profile.split(",",-1);String[] keys={"ready","type","deadzone","lines","ratio","diameter_milli","p_milli","i_milli","d_milli"};JSONObject p=new JSONObject();if(f.length==10){for(int i=0;i<9;i++)p.put(keys[i],Long.parseLong(f[i+1]));data.put("driver_profile",p);}}
    }
    data.put("camera",camera.status());data.put("recording",recorder.status());data.put("diagnostics",new JSONObject().put("ok",true).put("active",current!=null&&current.isBusy()).put("id",current==null?"—":current.session()).put("seq",current==null?0:current.persistedCount()).put("segments",1));return data;}
  public JSONObject getJson(String path)throws Exception{
    if(path.equals("ui/info"))return new JSONObject().put("demo",false).put("platform","android").put("vehicle_motion","CAPABILITY_GATED_MANUAL_FILMING")
      .put("source_package",getPackageName()).put("source_version",getPackageManager().getPackageInfo(getPackageName(),0).versionName)
      .put("transport_default","HTTP").put("bridge",new JSONObject().put("bound",board!=null).put("sampling_active",board!=null&&board.isBusy()).put("sample_age_ms",board==null?-1:board.sampleAge()).put("phase",board==null?"主控服务未绑定":board.phase()));
    if(path.equals("camera/compatibility"))return camera.compatibility();if(path.equals("status"))return snapshot();if(path.equals("camera/status"))return camera.status();if(path.equals("record/status"))return recorder.status();
    if(path.equals("record/list"))return null;throw new IllegalArgumentException("没有这个读取接口");
  }
  public Object read(String path)throws Exception{if(path.equals("photo/list"))return photos.list();if(path.equals("record/list"))return recorder.list();if(path.startsWith("record/")&&path.endsWith("/data"))return recorder.replay(path.substring(7,path.length()-5));return getJson(path);}
  public JSONObject post(String path,JSONObject body)throws Exception{
    JSONObject safe=new JSONObject();Iterator<String> keys=body.keys();while(keys.hasNext()){String key=keys.next();if(!key.equals("session"))safe.put(key,body.get(key));}audit("ui_request",path+" "+safe.toString());
    if(path.startsWith("drive/")){if(board==null)throw new IllegalStateException("主控服务未就绪");return board.driveCommand(path.substring(6),body);}
    if(path.equals("photo/capture"))return photos.capture(camera.capture(),snapshot());
    if(path.startsWith("gimbal/")){if(board==null)throw new IllegalStateException("主控服务未就绪");return board.remoteCommand(path.substring(7),body);}
    if(path.equals("camera/start"))return camera.start(body.getString("resolution"),body.getInt("fps"));
    if(path.equals("camera/stop")){recorder.stop("画面关闭");return camera.stop();}
    if(path.equals("record/start")){if(!camera.status().optBoolean("valid"))throw new IllegalStateException("相机需要有新鲜画面");return recorder.start(camera.status());}
    if(path.equals("record/stop"))return recorder.stop("用户停止");throw new IllegalArgumentException("没有这个写入接口");
  }
  public byte[] frame(String path,String query)throws Exception{if(path.equals("camera/frame"))return camera.frame();if(path.startsWith("record/")&&path.endsWith("/frame")){String id=path.substring(7,path.length()-6);if(!query.matches("index=[0-9]+"))throw new IllegalArgumentException("帧编号错误");return recorder.frameAt(id,Integer.parseInt(query.substring(6)));}throw new IllegalArgumentException("没有这个画面接口");}
  public File mediaFile(String path)throws Exception{
    if(path.matches("photo/[0-9]{8}-[0-9]{6}-[0-9a-f]{6}/(image|download)"))return photos.image(path.split("/")[1]);
    if(path.matches("record/[0-9]{8}-[0-9]{6}-[0-9a-f]{6}/(video|download)"))return recorder.mp4(path.split("/")[1]);
    throw new IllegalArgumentException("没有这个媒体文件");
  }
  public long frameSeq(){return camera.sequence();}
  public synchronized void audit(String event,String detail){try{JSONObject row=new JSONObject().put("event",event).put("detail",detail).put("elapsed_ms",SystemClock.elapsedRealtime()).put("wall_ms",System.currentTimeMillis());File file=new File(getFilesDir(),"web-events.jsonl");if(file.length()>8*1024*1024)file.renameTo(new File(getFilesDir(),"web-events-"+System.currentTimeMillis()+".jsonl"));try(FileOutputStream out=new FileOutputStream(file,true)){out.write((row.toString()+"\n").getBytes("UTF-8"));}}catch(Exception error){android.util.Log.e("ZXR_DASH","web log failed",error);}}
  public void onDestroy(){if(usbInventory!=null)usbInventory.close();if(http!=null)http.close();if(camera!=null)camera.close();if(recorder!=null)recorder.stop("服务结束");if(bound)unbindService(binding);if(wake!=null&&wake.isHeld())wake.release();super.onDestroy();}
}
