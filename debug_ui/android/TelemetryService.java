package cn.zhixing.dashboard;

import android.app.*;
import android.content.*;
import android.hardware.usb.*;
import android.os.*;
import android.util.Base64;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

/** One USB owner, foreground recording survives Activity backgrounding.
 * Every TX attempt, accepted portion, RX packet and parsed reply is retained.
 * Gimbal commands require its existing capability; drive commands additionally
 * require the version-2 native protocol and a separate explicit bench lease. */
public class TelemetryService extends Service {
    private final ControlBroker remoteControls=new ControlBroker();
    private final DriveBroker driveControls=new DriveBroker();
    private final LineTaskBroker lineTask=new LineTaskBroker();
    private LineCalibration calibration;
    private void initLineCalibration(){
      LineCalibration.Store store=json->{if(!getSharedPreferences("line_calibration",0).edit().putString("json",json).commit())throw new IOException("手机标定存储失败");};
      try{calibration=new LineCalibration(getSharedPreferences("line_calibration",0).getString("json",null),store);}catch(Exception error){android.util.Log.e("ZXR_DASH","Invalid line profile",error);try{calibration=new LineCalibration(null,store);}catch(Exception impossible){throw new IllegalStateException(impossible);}}
    }
    private boolean calibrationIdle()throws Exception{
      if(lineTask.active()||driveControls.publicState().optBoolean("active")||remoteControls.publicState().optBoolean("active"))return false;
      Map<String,String> rows=snapshot();String r=rows.get("DRIVE_STATUS"),g=rows.get("GIMBAL_STATUS");
      if(r==null||g==null)return false;String[] d=r.split(",",-1),p=g.split(",",-1);
      return d.length==10&&d[2].equals("0")&&d[3].equals("0")&&p.length==11&&p[3].equals("0");
    }
    public JSONObject lineCalibrationState()throws Exception{return calibration.state();}
    public JSONObject lineCalibrationCommand(String action)throws Exception{return calibration.command(action,calibrationIdle(),TelemetryCodec.decode(snapshot(),sampleAge(),busy,phase));}

    private volatile boolean lineTaskSupported,lineTaskGroundReady,lineTaskTrial,lineTaskLoop;
    private volatile boolean driveCapable,driveManual,driveNative,driveProfileVerified,driveFullSpeed;
    private volatile boolean lineCapable,mpuCapable,imuFeaturesCapable,driveMecanum;
    public boolean driveMecanum(){return driveMecanum;}
    public boolean driveNative(){return driveNative;}
    private volatile int drivePwmLimit,driveSpeedLimit;
    public int driveSpeedLimit(){return driveSpeedLimit;}
    public int drivePwmLimit(){return drivePwmLimit;}
    public boolean manualDriveAvailable(){return driveAvailable()&&driveManual&&!lineTask.active();}
    public JSONObject driveState()throws JSONException{return driveControls.publicState().put("protocol_version",driveMecanum?5:driveFullSpeed?4:driveNative?3:2).put("chassis",driveMecanum?"mecanum":"differential").put("control_model",driveNative?"driver_native_speed":"wheel_speed");}
    public boolean driveAvailable(){return gimbalAvailable()&&driveCapable&&(!driveNative||driveProfileVerified);}
    public JSONObject driveCommand(String action,JSONObject body)throws Exception{
        if(!action.equals("stop")&&remoteControls.following())throw new IOException("请先停止云台自动跟随，再开启车辆运动");
        if(!action.equals("stop")&&calibration.busy())throw new IOException("现场标定中，请先结束采样或保存");
        if(!manualDriveAvailable())throw new IOException("四驱协议未就绪，请核对新固件与主控记录状态");
        return driveControls.submit(action,body);
    }
    public JSONObject lineTaskState()throws JSONException{
        String why=!lineTaskSupported?"主控未部署自动循迹执行版":!lineTaskGroundReady?"主控巡线许可关闭，需更新主控":!gimbalAvailable()?"请先连接主控并开始记录":!calibration.ready()?"等待已保存标定恢复到主控；请查看现场标定提示":!driveAvailable()?"等待电机驱动板供电和反馈":driveControls.publicState().optBoolean("active")?"请先停止手动行驶":lineTaskTrial?"首轮试跑：低速5秒，路口停车；请先确认X1车侧":"巡线就绪";
        boolean available=lineTaskSupported&&lineTaskGroundReady&&calibration.ready()&&!calibration.busy()&&driveAvailable()&&driveManual&&sampleAge()<1500&&!driveControls.publicState().optBoolean("active");
        return lineTask.publicState().put("supported",lineTaskSupported).put("available",available).put("ground_ready",lineTaskGroundReady).put("trial",lineTaskTrial).put("loop_supported",lineTaskLoop).put("message",why);
    }
    public JSONObject lineTaskCommand(String action,JSONObject body)throws Exception{
        if(action.equals("start")&&remoteControls.following())throw new IOException("请先停止云台自动跟随，再启动循迹");
        if(!lineTaskSupported){if(action.equals("stop"))return new JSONObject().put("ok",true).put("unsupported",true).put("stopped",false);throw new IOException("主控未部署自动循迹执行版");}
        if(!action.equals("stop")&&!lineTaskState().optBoolean("available"))throw new IOException(lineTaskState().optString("message"));
        if(action.equals("start")&&(!calibration.ready()||calibration.busy()))throw new IOException("请先完成现场标定并核对主控参数");
        if(action.equals("start")&&lineTaskTrial&&(body.optInt("branch",-1)!=0||body.optInt("speed",0)!=40||body.optInt("duration_ms",0)>5000))throw new IOException("首轮仅开放低速、最长5秒、路口停车");
        if(action.equals("start")&&body.optInt("branch",-1)==4&&(!lineTaskLoop||body.optInt("speed",0)>40))throw new IOException("当前主控不支持该环线模式或速度过高");
        return lineTask.submit(action,body);
    }
    private void pumpControls(ControlBroker.Exchange exchange)throws Exception{
        if(lineTaskSupported)lineTask.pump(exchange);
        if(driveCapable)driveControls.pump(exchange);
        remoteControls.pump(exchange);
        calibration.pump(exchange,calibrationIdle());
    }
    public final NativeCamera nativeCamera=new NativeCamera();
    public JSONObject remoteState()throws JSONException{return remoteControls.publicState();}
    private String followBlockReason(){
        try{return FollowInterlock.blocked(snapshot(),gimbalAvailable(),sampleAge(),calibration.busy(),lineTask.active(),driveControls.publicState().optBoolean("active"));}
        catch(Exception error){return "车轮状态尚未确认。";}
    }
    private boolean followStationary(){return followBlockReason()==null;}
    public void followVision(java.util.function.Supplier<GimbalFollower.Frame> source){remoteControls.followSource(new GimbalFollower.Source(){
        public GimbalFollower.Frame latest(){return source.get();}public boolean stationary(){return followStationary();}
    });}
    public JSONObject followState()throws JSONException{String why=followBlockReason();return remoteControls.followState().put("supported",true).put("available",why==null).put("block_reason",why==null?JSONObject.NULL:why);}
    public JSONObject followCommand(String action,JSONObject body)throws Exception{
        if(!java.util.Arrays.asList("start","heartbeat","stop").contains(action))throw new IllegalArgumentException("没有这个跟随操作");
        if(!gimbalAvailable())throw new IOException("请先连接主控并开始记录");
        return remoteControls.submit("follow-"+action,body);
    }
    public JSONObject gimbalSettings()throws JSONException{return remoteControls.settings();}
    public JSONObject configureGimbal(JSONObject body)throws Exception{return remoteControls.configure(body);}
    private void initGimbalSettings(){
        ControlBroker.Store store=json->{if(!getSharedPreferences("gimbal_profile",0).edit().putString("json",json).commit())throw new IOException("云台参数未能保存");};
        try{remoteControls.persistence(getSharedPreferences("gimbal_profile",0).getString("json",null),store);}
        catch(Exception error){android.util.Log.e("ZXR_DASH","Invalid saved gimbal profile; using default",error);try{remoteControls.persistence(null,store);}catch(Exception ignored){}}
    }
    public JSONObject remoteCommand(String action,JSONObject body)throws Exception{
        if(!java.util.Arrays.asList("start","stop","set","center","heartbeat","calibrate").contains(action))throw new IllegalArgumentException("没有这个手动云台操作");
        if(!action.equals("stop")&&calibration.busy())throw new IOException("现场标定中，请先结束采样或保存");
        if(!gimbalAvailable())throw new IOException("云台控制未就绪，请先连接主控并开始记录");
        return remoteControls.submit(action,body);
    }
    public static final String START="cn.zhixing.dashboard.START",STOP="cn.zhixing.dashboard.STOP",DISCONNECT="cn.zhixing.dashboard.DISCONNECT";
    private UsbManager manager;private PowerManager.WakeLock wake;
    private volatile boolean busy=false,cancelled=true,journalDone,manualCapable;
    public boolean gimbalAvailable(){return busy&&!cancelled&&manualCapable&&sampleAge()>=0&&sampleAge()<5000;}
    private volatile UsbDeviceConnection connection;
    private volatile UsbInterface heldData,heldControl;private volatile String heldDeviceName;private volatile boolean disconnectWanted;
    private volatile UsbEndpoint readEndpoint;
    private volatile String phase="尚未连接",journalError,readerError,sessionId="—",stopReason="";
    private volatile long samples,replyTotal,lastSample=-1,persistedEvents,durableEvents;
    private final Map<String,String> latest=new HashMap<>();
    private final ByteArrayOutputStream pending=new ByteArrayOutputStream();
    private BlockingQueue<JSONObject> journalQueue;private BlockingQueue<String> receivedLines;
    private FileOutputStream journal;private Thread readerThread,journalThread,worker;
    private long eventSeq;private String deviceName;
    private volatile boolean uiVisible;
    public class LocalBinder extends Binder {public TelemetryService getService(){return TelemetryService.this;}}
    private final IBinder binder=new LocalBinder();
    public IBinder onBind(Intent i){return binder;}
    public boolean isBusy(){return busy;}public String phase(){return phase;}public String session(){return sessionId;}
    public long sampleAge(){return lastSample<0?-1:SystemClock.elapsedRealtime()-lastSample;}
    public long replyCount(){return replyTotal;}public long persistedCount(){return durableEvents;}
    public String logState(){return journalError!=null?"记录错误："+journalError:busy?"原始记录持续保存；约每秒同步到存储":"记录服务已停止";}
    public Map<String,String> snapshot(){synchronized(latest){return new HashMap<>(latest);}}
    public void noteVisibility(boolean visible){uiVisible=visible;if(busy&&journal!=null&&!journalDone)try{event("ui_visibility","visible",visible);}catch(Exception e){journalError=e.toString();cancelled=true;}}
    private boolean target(UsbDevice d){return d!=null&&d.getVendorId()==0x1a86&&d.getProductId()==0xfe0c;}
    private final BroadcastReceiver detach=new BroadcastReceiver(){public void onReceive(Context c,Intent i){UsbDevice d=i.getParcelableExtra(UsbManager.EXTRA_DEVICE);if(d!=null&&d.getDeviceName().equals(deviceName))requestStop("USB_DETACHED");}};
    public void onCreate(){super.onCreate();initGimbalSettings();initLineCalibration();manager=(UsbManager)getSystemService(USB_SERVICE);((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(new NotificationChannel("record","主控原始记录",NotificationManager.IMPORTANCE_LOW));registerReceiver(detach,new IntentFilter(UsbManager.ACTION_USB_DEVICE_DETACHED));wake=((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"zhixing:usb-record");}
    private Notification notification(){
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent disconnect=PendingIntent.getService(this,2,new Intent(this,TelemetryService.class).setAction(DISCONNECT),PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop=PendingIntent.getService(this,1,new Intent(this,TelemetryService.class).setAction(STOP),PendingIntent.FLAG_UPDATE_CURRENT);
        return new Notification.Builder(this,"record").setSmallIcon(android.R.drawable.stat_notify_sync).setContentTitle("知行回路 · 主控记录").setContentText(busy?"持续读取状态并保存原始通信":"记录已停止，USB连接保留").setContentIntent(open).setOngoing(true).addAction(new Notification.Action.Builder(null,"结束本段",stop).build()).addAction(new Notification.Action.Builder(null,"断开主控",disconnect).build()).build();
    }
    public int onStartCommand(Intent i,int flags,int id){
        if(i==null)return START_NOT_STICKY;
        if(DISCONNECT.equals(i.getAction())){requestDisconnect("USER_NOTIFICATION_DISCONNECT");return START_NOT_STICKY;}
        if(STOP.equals(i.getAction())){requestStop("USER_NOTIFICATION_STOP");return START_NOT_STICKY;}
        if(!START.equals(i.getAction()))return START_NOT_STICKY;
        startForeground(7,notification());
        if(busy)return START_NOT_STICKY;
        UsbDevice d=i.getParcelableExtra("device");
        if(!target(d)||!manager.hasPermission(d)){phase="没有有效的P7访问授权";stopForeground(true);stopSelf();return START_NOT_STICKY;}
        busy=true;cancelled=false;nativeCamera.reset(false);manualCapable=false;remoteControls.wideCapability(false);disconnectWanted=false;deviceName=d.getDeviceName();stopReason="";phase="正在建立记录与主控连接";
        samples=0;replyTotal=0;lastSample=-1;persistedEvents=0;durableEvents=0;synchronized(latest){latest.clear();}
        if(!wake.isHeld())wake.acquire();worker=new Thread(new Runnable(){public void run(){runSession(d);}},"car-telemetry-worker");worker.start();return START_NOT_STICKY;
    }
    public void requestStop(String reason){if("USB_DETACHED".equals(reason)){requestDisconnect(reason);return;}if(!busy)return;stopReason=reason;cancelled=true;phase="正在结束本段记录，USB连接保留";cancelReader();}
    public void requestDisconnect(String reason){disconnectWanted=true;if(busy){stopReason=reason;cancelled=true;phase="正在保存并断开主控";cancelReader();return;}closeLink(reason);phase="主控已断开，历史记录保留";if(wake.isHeld())wake.release();stopForeground(true);stopSelf();}
    private synchronized void closeLink(String reason){
        UsbDeviceConnection c=connection;UsbInterface d=heldData,ctrl=heldControl;connection=null;heldData=heldControl=null;heldDeviceName=null;readEndpoint=null;
        if(c==null)return;
        try{JSONObject row=new JSONObject();row.put("event","usb_link_closed");row.put("reason",reason);row.put("elapsed_ns",SystemClock.elapsedRealtimeNanos());row.put("wall_ms",System.currentTimeMillis());
            try(FileOutputStream f=new FileOutputStream(new File(getFilesDir(),"usb-lifecycle.jsonl"),true)){f.write((row.toString()+"\n").getBytes(StandardCharsets.UTF_8));f.getFD().sync();}
        }catch(Exception e){journalError="USB生命周期记录失败："+e.getMessage();}
        finally{try{if(d!=null)c.releaseInterface(d);}catch(Exception ignored){}try{if(ctrl!=null)c.releaseInterface(ctrl);}catch(Exception ignored){}c.close();}
    }
    static boolean retainAfterStop(boolean clean,boolean identified,boolean disconnectWanted,boolean present,String reason){
        return clean&&identified&&!disconnectWanted&&present&&("USER_STOP".equals(reason)||"USER_NOTIFICATION_STOP".equals(reason));
    }
    public void onDestroy(){requestDisconnect("SERVICE_DESTROYED");unregisterReceiver(detach);super.onDestroy();}
    private void runSession(UsbDevice device){
        UsbInterface control=null,data=null;UsbEndpoint input=null,output=null;
        File folder=null;String error=null;boolean clean=false,identified=false,keep=false;
        journal=null;journalThread=null;readerThread=null;readEndpoint=null;journalError=null;readerError=null;
        try{
            File parent=new File(getFilesDir(),"sessions");parent.mkdirs();
            if(parent.getUsableSpace()<64L*1024*1024)throw new IOException("手机剩余存储不足64MB，停止记录");
            sessionId=System.currentTimeMillis()+"-"+UUID.randomUUID().toString().substring(0,8);folder=new File(parent,sessionId);
            if(!folder.mkdirs())throw new IOException("不能创建记录目录");
            JSONObject info=new JSONObject();info.put("session",sessionId);info.put("version","dashboard-0.11");info.put("started_wall_ms",System.currentTimeMillis());info.put("mode","TELEMETRY_WITH_BOUNDED_GIMBAL");writeJson(new File(folder,"session.json"),info);
            startJournal(folder);event("session_started","version","dashboard-0.11","mode","TELEMETRY_WITH_BOUNDED_GIMBAL","vid_pid","1A86:FE0C","protocol","P7_NATIVE_BULK","sample_period_ms",1000,"clock","Android elapsedRealtimeNanos","motor_commands","VERSION2_BENCH_LEASE_ONLY","gimbal_commands","CAPABILITY_GATED_MANUAL_ONLY","ui_visible",uiVisible);
            int controls=0,datas=0;
            for(int i=0;i<device.getInterfaceCount();i++){
                UsbInterface f=device.getInterface(i);JSONArray eps=new JSONArray();
                for(int j=0;j<f.getEndpointCount();j++){UsbEndpoint ep=f.getEndpoint(j);JSONObject o=new JSONObject();o.put("address",ep.getAddress());o.put("type",ep.getType());o.put("packet_size",ep.getMaxPacketSize());eps.put(o);}
                event("usb_interface","id",f.getId(),"class",f.getInterfaceClass(),"subclass",f.getInterfaceSubclass(),"endpoints",eps);
                if(f.getInterfaceClass()==2&&f.getInterfaceSubclass()==2){control=f;controls++;}
                if(f.getInterfaceClass()==10){data=f;datas++;}
            }
            if(controls!=1||datas!=1)throw new IOException("没有唯一CDC串口接口，停止；不会试用调试接口");
            for(int i=0;i<data.getEndpointCount();i++){
                UsbEndpoint e=data.getEndpoint(i);if(e.getType()!=UsbConstants.USB_ENDPOINT_XFER_BULK)continue;
                if(e.getDirection()==UsbConstants.USB_DIR_IN)input=e;else output=e;
            }
            if(input==null||output==null)throw new IOException("串口收发端点不完整");
            boolean reuse=connection!=null&&heldData!=null&&heldControl!=null&&device.getDeviceName().equals(heldDeviceName);
            final UsbDeviceConnection conn;
            if(reuse){conn=connection;event("usb_connection_reused","device_name",device.getDeviceName(),"file_descriptor",conn.getFileDescriptor());}
            else{closeLink("OPEN_NEW_LINK");conn=manager.openDevice(device);if(conn==null)throw new IOException("无法打开USB设备");connection=conn;heldDeviceName=device.getDeviceName();event("usb_connection_opened","file_descriptor",conn.getFileDescriptor(),"permission",manager.hasPermission(device));}
            byte[] descriptors=conn.getRawDescriptors();event("usb_descriptors","data_b64",Base64.encodeToString(descriptors==null?new byte[0]:descriptors,Base64.NO_WRAP));
            /* Complete function ownership follows CDC control+data ordering.
             * Select only the data alternate setting; never reconfigure the device.
             * The installed lifecycle firmware clears affected DATA0 endpoint state.
             * Require real identity and advancing replies after setup succeeds. */
            if(!reuse){
                P7UsbSetup.prepare(conn,control,data,(name,id,accepted,duration)->event(name,"interface",id,"accepted",accepted,"duration_ms",duration,"usb_reconfigure",false));
                heldControl=control;heldData=data;
            }else event("native_interfaces_retained","control_interface",heldControl.getId(),"data_interface",heldData.getId(),"usb_reconfigure",false);
            phase="正在验证P7原生数据通道";
            startReader(conn,input);SystemClock.sleep(250);
            String identity=query(conn,output,"NATIVE_FEATURES","NORMAL_USBFS,");
            if(!identity.equals("NORMAL_USBFS,1")&&!identity.equals("NORMAL_USBFS,2"))throw new IOException("正常功能固件标识不符");
            event("native_features_verified","line",identity);identified=true;
            driveCapable=false;driveManual=false;driveNative=false;driveProfileVerified=false;driveFullSpeed=false;driveSpeedLimit=0;driveMecanum=false;driveControls.disconnect();driveControls.setMecanum(false);
            if(identity.equals("NORMAL_USBFS,2")){
                String driveCaps=query(conn,output,"DRIVE_CAPS","DRIVE_CAPS,");
                driveMecanum=driveCaps.equals("DRIVE_CAPS,5,250,600");
                String mecanumChassis=driveMecanum?query(conn,output,"DRIVE_CHASSIS","DRIVE_CHASSIS,"):"";
                driveControls.setMecanum(driveMecanum);
                driveFullSpeed=driveMecanum||driveCaps.equals("DRIVE_CAPS,4,250,600");driveNative=driveFullSpeed||driveCaps.equals("DRIVE_CAPS,3,250,600");driveCapable=driveNative||driveCaps.equals("DRIVE_CAPS,2,250,600");
                if(driveCapable){String driveId=query(conn,output,"DRIVE_ID","DRIVE_ID,");driveManual=false;drivePwmLimit=0;
                if(driveMecanum&&!MecanumLayout.matches(driveId,mecanumChassis))throw new IOException("麦轮固件与输出映射不符");
                if(driveId.startsWith("DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_")){
                  driveManual=query(conn,output,"DRIVE_MODE","DRIVE_MODE,").equals("DRIVE_MODE,MANUAL,1,0");
                  if(driveId.equals("DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_V3_20261021,1"))drivePwmLimit=375;
                  else{String[] limits=query(conn,output,"DRIVE_LIMITS","DRIVE_LIMITS,").split(",",-1);
                    if(limits.length!=5)throw new IOException("驱动输出范围回报格式不符");
                    drivePwmLimit=Integer.parseInt(limits[1]);driveSpeedLimit=Integer.parseInt(limits[4]);
                    if(driveNative){if(drivePwmLimit!=3600||!limits[2].equals("0")||!limits[3].equals("0")||driveSpeedLimit!=(driveFullSpeed?1000:120))throw new IOException("官方速度模式范围不符");}
                    else if(drivePwmLimit<375||drivePwmLimit>900)throw new IOException("驱动输出范围不受本版支持");}
                }}
                event(driveCapable?"drive_capability_verified":"drive_capability_unavailable","line",driveCaps,"mode","SPEED_V2_MANUAL_CAPABILITY_CHECKED");
            }
            String caps=query(conn,output,"GIMBAL_CAPS","GIMBAL_CAPS,");
            boolean wide=caps.equals("GIMBAL_CAPS,2,500,2500,4000");
            if(!wide&&!caps.equals("GIMBAL_CAPS,1"))throw new IOException("主控尚未安装本版云台控制固件");
            remoteControls.wideCapability(wide);
            event("gimbal_capability_verified","line",caps);manualCapable=true;
            String cameraCaps=query(conn,output,"CAMERA_CAPS","CAMERA_CAPS,");
            if(!cameraCaps.equals("CAMERA_CAPS,1,160,120"))throw new IOException("主控摄像头转发固件不符");
            event("camera_capability_verified","line",cameraCaps);nativeCamera.reset(true);

            lineCapable=false;
            try{lineCapable=query(conn,output,"LINE_ID","LINE_ID,").equals("LINE_ID,YB_8LP_UART4_PC10_PC11_STATIC_V1");}
            catch(Exception optional){event("line_capability_unavailable","reason",optional.toString());}
            mpuCapable=false;imuFeaturesCapable=false;
            try{mpuCapable=query(conn,output,"MPU_ID","MPU_ID,").equals("MPU_ID,MPU6050_PD6_PD7_ADDR69_V1");
                if(mpuCapable)imuFeaturesCapable=query(conn,output,"MPU_FEATURES_ID","MPU_FEATURES_ID,").equals("MPU_FEATURES_ID,IMU_OBSERVER_V1_20HZ");}
            catch(Exception optional){event("mpu_capability_unavailable","reason",optional.toString());}
            lineTaskSupported=false;lineTaskGroundReady=false;lineTask.disconnect();
            try{String taskCaps=query(conn,output,"LINE_TASK_CAPS","LINE_TASK_CAPS,");
                lineTaskSupported=taskCaps.equals("LINE_TASK_CAPS,1,50,100,0")||taskCaps.equals("LINE_TASK_CAPS,1,50,100,1");lineTaskGroundReady=taskCaps.endsWith(",1")&&lineTaskSupported;
                event("line_task_capability","line",taskCaps);}
            catch(Exception optional){event("line_task_unavailable","reason",optional.toString());}
            lineTaskTrial=false;
            if(lineTaskSupported)try{lineTaskTrial=query(conn,output,"LINE_TASK_TRIAL","LINE_TASK_TRIAL,").equals("LINE_TASK_TRIAL,1,40,5000");}catch(Exception optional){event("line_task_trial_unavailable","reason",optional.toString());}
            lineTaskLoop=false;
            if(lineTaskSupported)try{lineTaskLoop=query(conn,output,"LINE_TASK_LOOP","LINE_TASK_LOOP,").matches("LINE_TASK_LOOP,1,40,(0|800)");}catch(Exception optional){event("line_task_loop_unavailable","reason",optional.toString());}
            final String[] commands={"STATUS","ULTRA_STATUS","GIMBAL_STATUS","MUTE_STATUS","PARAM_STATUS","RECOVERY_STATUS","OLED_SCREEN","OLED2_SCREEN","OLED3_SCREEN","MOTOR_DASH_STATUS","DRIVE_STATUS","DRIVE_ACTUATORS","DRIVE_PROFILE","LINE_ANALOG","LINE_DIGITAL","LINE_STATUS","MPU_RAW","MPU_STATUS","MPU_FEATURES","LINE_TASK_STATUS"};
            final String[] prefixes={"STATUS,","ULTRA,","GIMBAL,","MUTE,","PARAM,","RECOVERY,","SCREEN,","SCREEN2,","SCREEN3,","MOTORDASH,","DRIVE,","ACTUATORS,","DRIVE_PROFILE,","LINE_ANALOG,","LINE_DIGITAL,","LINE_STATUS,","MPU_RAW,","MPU_STATUS,","MPU_FEATURES,","LINE_TASK_STATUS,"};
            final int[] counts={11,12,10,5,4,9,3,3,3,14,9,10,9,10,3,12,9,11,17,10};long previous=-1;
            phase="主控已连接，正在持续记录";
            final UsbEndpoint writeEndpoint=output;
            ControlBroker.Exchange exchange=new ControlBroker.Exchange(){public String call(String command,String prefix)throws Exception{
              // Recheck at the single USB write boundary, including jobs queued before capture.
              if(calibration.busy()&&(command.equals("DRIVE_ARM")||command.startsWith("DRIVE_SET,")||command.startsWith("DRIVE_BRAKE,")||command.equals("GIMBAL_MANUAL_START")||command.startsWith("GIMBAL_SET,")||command.equals("LINE_TASK_START")))throw new IOException("现场标定中，机构开启请求已撤销");
              String answer=query(conn,writeEndpoint,command,prefix);event("controller_exchange_reply","command",command,"line",answer);return answer;}};
            try{calibration.connect(exchange);}catch(Exception optional){event("line_calibration_unavailable","reason",optional.toString());}
            while(!cancelled){
                long began=SystemClock.elapsedRealtime(),mpuBegan=-1,lineBegan=-1;Map<String,String> cycle=new HashMap<>();
                cycle.put("MPU_CAPABLE",mpuCapable?"1":"0");
                for(int k=0;k<commands.length&&!cancelled;k++){
                    if(k>=13&&k<=15&&!lineCapable)continue;
                    if(k>=16&&k<=18&&!mpuCapable)continue;
                    if(k==19&&!lineTaskSupported)continue;
                    if(k==18&&!imuFeaturesCapable)continue;
                    if(k==16)mpuBegan=SystemClock.elapsedRealtime();
                    if(k==13)lineBegan=SystemClock.elapsedRealtime();
                    if(k>=10&&k<=12&&!driveCapable)continue;
                    if(k==12&&!driveNative)continue;
                    pumpControls(exchange);
                    try{
                    String reply=query(conn,output,commands[k],prefixes[k]);String[] f=reply.split(",",-1);
                    if(f.length!=counts[k]+1||!reply.startsWith(prefixes[k]))throw new IOException("状态格式错误："+commands[k]);
                    for(int n=1;n<f.length;n++)Long.parseLong(f[n]);
                    event("query_reply","command",commands[k],"line",reply,"cycle",samples+1);++replyTotal;cycle.put(commands[k],reply);
                    if(k==12)driveProfileVerified=f[1].equals("1");
                    if(k==0){long now=Long.parseLong(f[1]);if(previous>=0&&now<=previous)throw new IOException("主控运行时间回退或停止，需重新连接");previous=now;}
                    }catch(Exception optional){if(k<16)throw optional;
                        if(k==19){lineTaskSupported=false;lineTaskGroundReady=false;lineTask.disconnect();event("line_task_status_failed","reason",optional.toString());}
                        else{mpuCapable=false;imuFeaturesCapable=false;cycle.remove("MPU_RAW");cycle.remove("MPU_STATUS");cycle.remove("MPU_FEATURES");
                        cycle.put("MPU_QUERY_ERROR",optional.toString());event("mpu_readonly_query_failed","reason",optional.toString());}}
                }
                if(cancelled)break;
                if(mpuBegan>=0)cycle.put("MPU_HOST_AGE","MPU_HOST_AGE,"+(SystemClock.elapsedRealtime()-mpuBegan));
                if(lineBegan>=0)cycle.put("LINE_HOST_AGE","LINE_HOST_AGE,"+(SystemClock.elapsedRealtime()-lineBegan));
                if(lineTaskSupported)lineTask.observe(cycle.get("LINE_TASK_STATUS"));
                if(driveCapable)driveControls.observe(cycle.get("DRIVE_STATUS"));
                ++samples;synchronized(latest){latest.clear();latest.putAll(cycle);}lastSample=SystemClock.elapsedRealtime();
                calibration.observe(TelemetryCodec.decode(cycle,0,true,phase),calibrationIdle());
                event("sample_complete","cycle",samples,"fields",new JSONObject(cycle));
                nativeCamera.pump(exchange,()->pumpControls(exchange));
                if(samples%10==0){Intent battery=registerReceiver(null,new IntentFilter(Intent.ACTION_BATTERY_CHANGED));if(battery!=null)event("phone_power","level",battery.getIntExtra(BatteryManager.EXTRA_LEVEL,-1),"scale",battery.getIntExtra(BatteryManager.EXTRA_SCALE,-1),"temperature_tenths_c",battery.getIntExtra(BatteryManager.EXTRA_TEMPERATURE,-1),"plugged",battery.getIntExtra(BatteryManager.EXTRA_PLUGGED,0));if(parent.getUsableSpace()<64L*1024*1024)throw new IOException("存储不足64MB，停止记录");}
                long left=1000-(SystemClock.elapsedRealtime()-began);while(left>0&&!cancelled){pumpControls(exchange);SystemClock.sleep(Math.min(left,50));left=1000-(SystemClock.elapsedRealtime()-began);}
            }
            if(journalError!=null||readerError!=null)throw new IOException(journalError!=null?journalError:readerError);
            event("session_finished","reason",stopReason,"cycles",samples,"queries",replyTotal);clean=true;
        }catch(Exception e){
            error=e.toString();
            if(cancelled&&journalError==null&&readerError==null&&!stopReason.isEmpty()){
                try{event("session_finished","reason",stopReason,"cycles",samples,"queries",replyTotal,"query_interrupted",true);clean=true;error=null;}catch(Exception log){error=log.toString();}
            }else try{if(journal!=null)event("session_error","error",error,"cycles",samples);}catch(Exception ignored){}
        }finally{
            manualCapable=false;remoteControls.wideCapability(false);driveCapable=false;driveManual=false;driveNative=false;driveProfileVerified=false;driveFullSpeed=false;driveSpeedLimit=0;driveMecanum=false;driveControls.disconnect();driveControls.setMecanum(false);driveNative=false;nativeCamera.reset(false);remoteControls.disconnect();driveControls.disconnect();lineTask.disconnect();lineTaskSupported=false;lineTaskGroundReady=false;
            calibration.disconnect();cancelled=true;cancelReader();
            keep=retainAfterStop(clean,identified,disconnectWanted,manager.getDeviceList().containsKey(deviceName),stopReason);
            if(keep){try{event("usb_connection_retained","device_name",deviceName);}catch(Exception e){journalError=e.toString();keep=false;}}
            if(!keep)closeLink("SESSION_END:"+stopReason);
            try{if(readerThread!=null)readerThread.join(1500);}catch(InterruptedException ignored){}
            journalDone=true;try{if(journalThread!=null)journalThread.join(3000);}catch(InterruptedException ignored){}
            boolean lingering=(readerThread!=null&&readerThread.isAlive())||(journalThread!=null&&journalThread.isAlive());
            if(lingering||journalError!=null){keep=false;closeLink("RECORD_FINALIZE_ERROR");clean=false;if(error==null)error="日志或接收线程未正常关闭";}
            if(folder!=null)try{JSONObject end=new JSONObject();end.put("session",sessionId);end.put("clean_close",clean);end.put("usb_connection_retained",keep);end.put("reason",stopReason);end.put("error",error==null?JSONObject.NULL:error);end.put("cycles",samples);end.put("queries",replyTotal);end.put("events",persistedEvents);end.put("ended_wall_ms",System.currentTimeMillis());writeJson(new File(folder,"result.json"),end);}catch(Exception e){clean=false;error="汇总保存失败："+e.getMessage();}
            lastSample=-1;phase=clean?(keep?"记录已保存，主控连接保留；可开始下一段":stopReason.equals("USB_DETACHED")?"USB已断开，记录已保存":"记录已保存，主控已断开"):"记录停止："+error;
            if(lingering)phase+="；请关闭应用后重新打开";
            if(keep){busy=lingering;((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).notify(7,notification());}
            else{if(wake.isHeld())wake.release();stopForeground(true);stopSelf();busy=lingering;}
        }
    }
    private void writeJson(File file,JSONObject json)throws Exception{
        File temp=new File(file.getParentFile(),file.getName()+".tmp");
        try(FileOutputStream f=new FileOutputStream(temp)){f.write(json.toString().getBytes(StandardCharsets.UTF_8));f.getFD().sync();}
        if(!temp.renameTo(file))throw new IOException("记录元数据保存失败");
    }
    private synchronized void event(String name,Object... pairs)throws Exception{
        JSONObject row=new JSONObject();row.put("seq",++eventSeq);row.put("elapsed_ns",SystemClock.elapsedRealtimeNanos());row.put("wall_ms",System.currentTimeMillis());row.put("event",name);row.put("session",sessionId);
        for(int i=0;i<pairs.length;i+=2)row.put((String)pairs[i],pairs[i+1]);
        if(journalError!=null)throw new IOException("日志写入失败："+journalError);
        if(!journalQueue.offer(row)){journalError="日志队列满，记录不完整";cancelled=true;throw new IOException(journalError);}
    }
    private void startJournal(File folder)throws IOException{
        journal=new FileOutputStream(new File(folder,"events.jsonl"));eventSeq=0;
        journalQueue=new ArrayBlockingQueue<JSONObject>(1024);journalDone=false;journalError=null;readerError=null;
        journalThread=new Thread(new Runnable(){public void run(){
            long synced=SystemClock.elapsedRealtime();
            try{
                while(!journalDone||!journalQueue.isEmpty()){
                    JSONObject row=journalQueue.poll(100,TimeUnit.MILLISECONDS);
                    if(row!=null){journal.write((row.toString()+"\n").getBytes(StandardCharsets.UTF_8));++persistedEvents;}
                    if(SystemClock.elapsedRealtime()-synced>=1000){journal.flush();journal.getFD().sync();durableEvents=persistedEvents;synced=SystemClock.elapsedRealtime();}
                }
                journal.flush();journal.getFD().sync();durableEvents=persistedEvents;
            }catch(Exception error){journalError=error.toString();cancelled=true;}
            finally{try{journal.close();}catch(IOException error){journalError=error.toString();}}
        }},"board-log-writer");journalThread.start();
    }
    private void startReader(final UsbDeviceConnection conn,final UsbEndpoint input)throws Exception{
        receivedLines=new ArrayBlockingQueue<String>(128);pending.reset();readEndpoint=input;
        event("reader_armed","mode","SINGLE_WORKER_BULK","read_timeout_ms",250,"query_deadline_ms",3000);
    }
    private void cancelReader(){readEndpoint=null;}
    private void raw(String direction,byte[] bytes,int length)throws Exception{
        event("uart_bytes","direction",direction,"length",length,"data_b64",Base64.encodeToString(Arrays.copyOf(bytes,length),Base64.NO_WRAP));
    }

    private String query(UsbDeviceConnection conn,UsbEndpoint output,String command,String prefix)throws Exception{
        if(cancelled)throw new IOException("用户停止或USB断开");
        byte[] tx=(command+"\n").getBytes(StandardCharsets.US_ASCII);raw("TX_ATTEMPT",tx,tx.length);
        long sentAt=SystemClock.elapsedRealtime();int sent=conn.bulkTransfer(output,tx,tx.length,1000);event("usb_write_result","result",sent,"requested",tx.length,"duration_ms",SystemClock.elapsedRealtime()-sentAt,"command",command);if(sent>0)raw("TX_ACCEPTED",tx,sent);
        if(sent!=tx.length){
            if(command.equals("NATIVE_FEATURES")&&!cancelled){byte[] statusBytes=new byte[2];long at=SystemClock.elapsedRealtime();int n=conn.controlTransfer(0x80,0,0,0,statusBytes,2,300);event("usb_device_status_after_first_write_failure","result",n,"duration_ms",SystemClock.elapsedRealtime()-at,"data_b64",Base64.encodeToString(Arrays.copyOf(statusBytes,Math.max(0,Math.min(2,n))),Base64.NO_WRAP));}
            throw new IOException("发送不完整："+command);
        }
        long deadline=SystemClock.elapsedRealtime()+3000;byte[] buffer=new byte[64];
        while(!cancelled&&SystemClock.elapsedRealtime()<deadline){
            if(journalError!=null)throw new IOException(journalError);
            String found;
            while((found=receivedLines.poll())!=null){
                if(found.startsWith(prefix))return found;
                if(BoardReplyException.rejects(command,found)){
                    event("control_rejected","command",command,"line",found);
                    throw new BoardReplyException(found);
                }
                event("unexpected_reply","expected",prefix,"line",found);
            }
            UsbEndpoint input=readEndpoint;if(input==null)break;
            long started=SystemClock.elapsedRealtime();
            int timeout=(int)Math.min(250,Math.max(1,deadline-started));
            int n=conn.bulkTransfer(input,buffer,buffer.length,timeout);
            long spent=SystemClock.elapsedRealtime()-started;
            if(n>=0){
                if(n>buffer.length)throw new IOException("USB接收长度异常");
                raw("RX",buffer,n);
                if(n==0)event("usb_empty_read","duration_ms",spent);
            }else{
                // This API returns a negative value for failure, without exposing errno.
                // Never label it a timeout or invent RX bytes. The query still needs a real reply.
                event("usb_read_negative","result",n,"duration_ms",spent,"timeout_ms",timeout,"command",command);
            }
            if(n<=0){
                if(!cancelled)SystemClock.sleep(Math.min(100,Math.max(0,deadline-SystemClock.elapsedRealtime())));
                continue;
            }
            for(int j=0;j<n;j++){
                if(buffer[j]=='\n'){
                    String line=new String(pending.toByteArray(),StandardCharsets.US_ASCII);pending.reset();
                    if(!receivedLines.offer(line))throw new IOException("回复队列满，记录不完整");
                }else{
                    if(pending.size()>=4096)throw new IOException("回复超出上限，原始字节保留");pending.write(buffer[j]);
                }
            }
        }
        if(journalError!=null)throw new IOException(journalError);
        throw new IOException(cancelled?"用户停止":"等待主控回复超时："+command);
    }

}
