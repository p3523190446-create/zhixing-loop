package cn.zhixing.carconsole;

import android.app.*;
import android.content.*;
import android.hardware.usb.*;
import android.os.*;
import android.util.Base64;
import org.json.*;
import java.io.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

/** One USB owner, foreground recording survives Activity backgrounding.
 * Every TX attempt, accepted portion, RX packet and parsed reply is retained.
 * This service has no movement/settings writes or automatic reconnect/arm. */
public class TelemetryService extends Service {
    public static final String START="cn.zhixing.carconsole.START",STOP="cn.zhixing.carconsole.STOP";
    private UsbManager manager;private PowerManager.WakeLock wake;
    private volatile boolean busy=false,cancelled=true,journalDone;
    private volatile UsbDeviceConnection connection;
    private volatile UsbRequest[] readerRequests;
    private volatile String phase="尚未连接",journalError,readerError,sessionId="—",stopReason="";
    private volatile long samples,replyTotal,lastSample=-1,persistedEvents,durableEvents;
    private final Map<String,String> latest=new HashMap<>();
    private final ByteArrayOutputStream pending=new ByteArrayOutputStream();
    private BlockingQueue<JSONObject> journalQueue;private BlockingQueue<String> receivedLines;
    private FileOutputStream journal;private Thread readerThread,journalThread,worker;
    private long eventSeq;private String deviceName;
    private volatile boolean uiVisible;
    private CarWebServer web;private volatile boolean hostWanted;private String webError;
    private volatile long recordStarted,recordEnded;
    public static final String HOST_START="cn.zhixing.carconsole.HOST_START",HOST_STOP="cn.zhixing.carconsole.HOST_STOP";
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
    public void onCreate(){super.onCreate();manager=(UsbManager)getSystemService(USB_SERVICE);((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(new NotificationChannel("record","主控原始记录",NotificationManager.IMPORTANCE_LOW));registerReceiver(detach,new IntentFilter(UsbManager.ACTION_USB_DEVICE_DETACHED));wake=((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"zhixing:usb-record");wake.setReferenceCounted(false);web=new CarWebServer(this);try{web.start();}catch(Exception e){webError=e.getMessage();phase="网页服务未启动："+webError;}}
    public String webUrl(){return webError==null?web.local():null;}
    public JSONArray webUrls(){return web.urls();}
    public void startHost(){startForegroundService(new Intent(this,TelemetryService.class).setAction(HOST_START));}
    private Notification notification(){
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop=PendingIntent.getService(this,1,new Intent(this,TelemetryService.class).setAction(STOP),PendingIntent.FLAG_UPDATE_CURRENT);
        return new Notification.Builder(this,"record").setSmallIcon(android.R.drawable.stat_notify_sync).setContentTitle("知行回路 · 主控记录").setContentText("持续读取状态并保存原始通信").setContentIntent(open).setOngoing(true).addAction(new Notification.Action.Builder(null,"停止记录",stop).build()).build();
    }
    public int onStartCommand(Intent i,int flags,int id){
        if(i==null)return START_NOT_STICKY;
        if(HOST_START.equals(i.getAction())){if(webError!=null){phase="网页服务未启动："+webError;return START_NOT_STICKY;}hostWanted=true;startForeground(7,notification());if(!wake.isHeld())wake.acquire();return START_NOT_STICKY;}
        if(HOST_STOP.equals(i.getAction())){hostWanted=false;requestStop("WEB_HOST_STOP");if(!busy){if(wake.isHeld())wake.release();stopForeground(true);stopSelf();}return START_NOT_STICKY;}
        if(STOP.equals(i.getAction())){requestStop("USER_NOTIFICATION_STOP");return START_NOT_STICKY;}
        if(!START.equals(i.getAction()))return START_NOT_STICKY;
        startForeground(7,notification());
        if(busy)return START_NOT_STICKY;
        UsbDevice d=i.getParcelableExtra("device");
        if(!target(d)||!manager.hasPermission(d)){phase="没有有效的P7访问授权";if(!hostWanted){stopForeground(true);stopSelf();}return START_NOT_STICKY;}
        busy=true;cancelled=false;deviceName=d.getDeviceName();stopReason="";phase="正在建立记录与主控连接";
        samples=0;replyTotal=0;lastSample=-1;persistedEvents=0;durableEvents=0;synchronized(latest){latest.clear();}
        recordStarted=SystemClock.elapsedRealtime();recordEnded=0;if(!wake.isHeld())wake.acquire();worker=new Thread(new Runnable(){public void run(){runSession(d);}},"car-telemetry-worker");worker.start();return START_NOT_STICKY;
    }
    public void requestStop(String reason){if(!busy)return;stopReason=reason;cancelled=true;phase="正在结束记录";cancelReader();UsbDeviceConnection c=connection;if(c!=null)c.close();}
    public void onDestroy(){hostWanted=false;requestStop("SERVICE_DESTROYED");if(web!=null)web.close();if(wake.isHeld())wake.release();unregisterReceiver(detach);super.onDestroy();}
    public JSONObject webStatus()throws Exception{
        long age=sampleAge();JSONObject o=WebState.decode(snapshot(),busy&&age>=0&&age<2500,age,System.currentTimeMillis()-Math.max(age,0));
        JSONObject caps=new JSONObject();caps.put("raw_record",true);caps.put("gimbal",false);caps.put("camera",false);caps.put("vehicle_motion",false);o.put("capabilities",caps);
        JSONObject diag=new JSONObject();diag.put("ok",journalError==null);diag.put("active",busy&&!journalDone);diag.put("id",sessionId);diag.put("seq",durableEvents);diag.put("segments",sessionId.equals("—")?0:1);diag.put("error",journalError==null?JSONObject.NULL:journalError);o.put("diagnostics",diag);return o;
    }
    public JSONObject webRecordStatus()throws Exception{
        JSONObject o=new JSONObject();o.put("active",busy&&!cancelled);o.put("finishing",busy&&cancelled);o.put("id",sessionId.equals("—")?JSONObject.NULL:sessionId);o.put("duration_s",Math.max(0,(busy?SystemClock.elapsedRealtime():recordEnded)-recordStarted)/1000.0);o.put("samples",samples);o.put("frames",0);o.put("queries",replyTotal);File f=new File(getFilesDir(),"sessions/"+sessionId+"/events.jsonl");o.put("bytes",f.isFile()?f.length():0);o.put("reason",stopReason);o.put("error",journalError==null?JSONObject.NULL:journalError);o.put("kind","RAW_TELEMETRY");return o;
    }
    public void beginFromWeb()throws Exception{
        if(busy)throw new IOException("记录正在运行或保存，请稍后操作");UsbDevice found=null;int n=0;for(UsbDevice d:manager.getDeviceList().values())if(target(d)){found=d;n++;}
        if(n!=1||!manager.hasPermission(found))throw new IOException("请先在小手机上连接主控并允许USB访问");
        startForegroundService(new Intent(this,TelemetryService.class).setAction(START).putExtra("device",found));
    }
    public void webEvent(String action,JSONObject body)throws Exception{
        JSONObject e=new JSONObject();e.put("event","web_action");e.put("action",action);e.put("body",body);e.put("elapsed_ns",SystemClock.elapsedRealtimeNanos());e.put("wall_ms",System.currentTimeMillis());
        try(FileOutputStream f=new FileOutputStream(new File(getFilesDir(),"web-actions.jsonl"),true)){f.write((e.toString()+"\n").getBytes(StandardCharsets.UTF_8));f.getFD().sync();}
        if(busy&&journal!=null&&!journalDone)event("web_action","action",action,"body",body);
    }
    private void runSession(UsbDevice device){
        UsbInterface control=null,data=null;UsbEndpoint input=null,output=null;
        File folder=null;String error=null;boolean clean=false;
        journal=null;journalThread=null;readerThread=null;readerRequests=null;journalError=null;readerError=null;
        try{
            File parent=new File(getFilesDir(),"sessions");parent.mkdirs();
            if(parent.getUsableSpace()<64L*1024*1024)throw new IOException("手机剩余存储不足64MB，停止记录");
            sessionId=System.currentTimeMillis()+"-"+UUID.randomUUID().toString().substring(0,8);folder=new File(parent,sessionId);
            if(!folder.mkdirs())throw new IOException("不能创建记录目录");
            JSONObject info=new JSONObject();info.put("session",sessionId);info.put("version","0.3");info.put("started_wall_ms",System.currentTimeMillis());info.put("mode","CONTINUOUS_READ_ONLY");writeJson(new File(folder,"session.json"),info);
            startJournal(folder);event("session_started","version","0.3","mode","CONTINUOUS_READ_ONLY","vid_pid","1A86:FE0C","baud",115200,"sample_period_ms",1000,"clock","Android elapsedRealtimeNanos","motion_commands",false,"ui_visible",uiVisible);
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
            UsbDeviceConnection conn=manager.openDevice(device);if(conn==null)throw new IOException("无法打开USB设备");connection=conn;
            byte[] descriptors=conn.getRawDescriptors();event("usb_descriptors","data_b64",Base64.encodeToString(descriptors==null?new byte[0]:descriptors,Base64.NO_WRAP));
            byte[] usbStatus=new byte[2];int statusLength=conn.controlTransfer(0x80,0,0,0,usbStatus,2,1000);
            event("usb_device_status","result",statusLength,"bytes_b64",Base64.encodeToString(statusLength>0?Arrays.copyOf(usbStatus,Math.min(statusLength,2)):new byte[0],Base64.NO_WRAP));
            byte[] config=new byte[1];int configLength=conn.controlTransfer(0x80,8,0,0,config,1,1000);
            event("usb_configuration","result",configLength,"configuration",configLength==1?(config[0]&255):-1,"available_configurations",device.getConfigurationCount());
            if(!conn.claimInterface(control,true)||!conn.claimInterface(data,true))throw new IOException("串口接口占用失败");
            byte[] line={(byte)0x00,(byte)0xc2,(byte)0x01,0,0,0,8};
            int setup=conn.controlTransfer(0x21,0x20,0,control.getId(),line,line.length,1000);
            event("cdc_line_coding","result",setup,"attempt",1,"bytes_b64",Base64.encodeToString(line,Base64.NO_WRAP));
            if(setup<0&&!cancelled){
                phase="串口设置失败，正在恢复一次";
                conn.releaseInterface(data);conn.releaseInterface(control);
                if(device.getConfigurationCount()!=1)throw new IOException("USB配置不唯一，停止恢复");
                boolean configured=conn.setConfiguration(device.getConfiguration(0));
                event("usb_reconfigure","configuration",device.getConfiguration(0).getId(),"accepted",configured);
                if(!configured)throw new IOException("USB重新配置未接受，停止本轮");
                if(!conn.claimInterface(control,true)||!conn.claimInterface(data,true))throw new IOException("USB恢复后串口接口占用失败");
                SystemClock.sleep(300);
                setup=conn.controlTransfer(0x21,0x20,0,control.getId(),line,line.length,1000);
                event("cdc_line_coding","result",setup,"attempt",2,"bytes_b64",Base64.encodeToString(line,Base64.NO_WRAP));
            }
            if(setup<0)throw new IOException("USB恢复后115200串口设置仍失败（"+setup+"），停止本轮");
            byte[] actual=new byte[7];int got=conn.controlTransfer(0xa1,0x21,0,control.getId(),actual,actual.length,1000);
            event("cdc_line_coding_readback","result",got,"bytes_b64",Base64.encodeToString(got>0?Arrays.copyOf(actual,Math.min(got,7)):new byte[0],Base64.NO_WRAP));
            if(got!=7||!Arrays.equals(line,actual))throw new IOException("串口参数未完整读回或不一致");
            int handshake=conn.controlTransfer(0x21,0x22,3,control.getId(),null,0,1000);event("cdc_control_lines","result",handshake);if(handshake<0)throw new IOException("串口控制设置失败");
            startReader(conn,input);SystemClock.sleep(250);
            String identity=query(conn,output,"NATIVE_FEATURES","NORMAL_USBFS,");
            if(!identity.equals("NORMAL_USBFS,1"))throw new IOException("正常功能固件标识不符");
            event("native_features_verified","line",identity);

            final String[] commands={"STATUS","ULTRA_STATUS","GIMBAL_STATUS","MUTE_STATUS","PARAM_STATUS","RECOVERY_STATUS","OLED_SCREEN","OLED2_SCREEN","OLED3_SCREEN","MOTOR_DASH_STATUS"};
            final String[] prefixes={"STATUS,","ULTRA,","GIMBAL,","MUTE,","PARAM,","RECOVERY,","SCREEN,","SCREEN2,","SCREEN3,","MOTORDASH,"};
            final int[] counts={11,12,10,5,4,9,3,3,3,14};long previous=-1;
            phase="主控已连接，正在持续记录";
            while(!cancelled){
                long began=SystemClock.elapsedRealtime();Map<String,String> cycle=new HashMap<>();
                for(int k=0;k<commands.length&&!cancelled;k++){
                    String reply=query(conn,output,commands[k],prefixes[k]);String[] f=reply.split(",",-1);
                    if(f.length!=counts[k]+1||!reply.startsWith(prefixes[k]))throw new IOException("状态格式错误："+commands[k]);
                    for(int n=1;n<f.length;n++)Long.parseLong(f[n]);
                    event("query_reply","command",commands[k],"line",reply,"cycle",samples+1);++replyTotal;cycle.put(commands[k],reply);
                    if(k==0){long now=Long.parseLong(f[1]);if(previous>=0&&now<=previous)throw new IOException("主控运行时间回退或停止，需重新连接");previous=now;}
                }
                if(cancelled)break;
                ++samples;synchronized(latest){latest.clear();latest.putAll(cycle);}lastSample=SystemClock.elapsedRealtime();
                event("sample_complete","cycle",samples,"fields",new JSONObject(cycle));
                if(samples%10==0){Intent battery=registerReceiver(null,new IntentFilter(Intent.ACTION_BATTERY_CHANGED));if(battery!=null)event("phone_power","level",battery.getIntExtra(BatteryManager.EXTRA_LEVEL,-1),"scale",battery.getIntExtra(BatteryManager.EXTRA_SCALE,-1),"temperature_tenths_c",battery.getIntExtra(BatteryManager.EXTRA_TEMPERATURE,-1),"plugged",battery.getIntExtra(BatteryManager.EXTRA_PLUGGED,0));if(parent.getUsableSpace()<64L*1024*1024)throw new IOException("存储不足64MB，停止记录");}
                long left=1000-(SystemClock.elapsedRealtime()-began);while(left>0&&!cancelled){SystemClock.sleep(Math.min(left,100));left=1000-(SystemClock.elapsedRealtime()-began);}
            }
            if(journalError!=null||readerError!=null)throw new IOException(journalError!=null?journalError:readerError);
            event("session_finished","reason",stopReason,"cycles",samples,"queries",replyTotal);clean=true;
        }catch(Exception e){
            error=e.toString();
            if(cancelled&&journalError==null&&readerError==null&&!stopReason.isEmpty()){
                try{event("session_finished","reason",stopReason,"cycles",samples,"queries",replyTotal,"query_interrupted",true);clean=true;error=null;}catch(Exception log){error=log.toString();}
            }else try{if(journal!=null)event("session_error","error",error,"cycles",samples);}catch(Exception ignored){}
        }finally{
            cancelled=true;cancelReader();UsbDeviceConnection c=connection;connection=null;
            if(c!=null){try{if(data!=null)c.releaseInterface(data);if(control!=null)c.releaseInterface(control);}catch(Exception ignored){}c.close();}
            try{if(readerThread!=null)readerThread.join(1500);}catch(InterruptedException ignored){}
            journalDone=true;try{if(journalThread!=null)journalThread.join(3000);}catch(InterruptedException ignored){}
            boolean lingering=(readerThread!=null&&readerThread.isAlive())||(journalThread!=null&&journalThread.isAlive());
            if(lingering||journalError!=null){clean=false;if(error==null)error="日志或接收线程未正常关闭";}
            if(folder!=null)try{JSONObject end=new JSONObject();end.put("session",sessionId);end.put("clean_close",clean);end.put("reason",stopReason);end.put("error",error==null?JSONObject.NULL:error);end.put("cycles",samples);end.put("queries",replyTotal);end.put("events",persistedEvents);end.put("ended_wall_ms",System.currentTimeMillis());writeJson(new File(folder,"result.json"),end);}catch(Exception e){clean=false;error="汇总保存失败："+e.getMessage();}
            recordEnded=SystemClock.elapsedRealtime();lastSample=-1;phase=clean?(stopReason.equals("USB_DETACHED")?"USB已断开，记录已保存":"记录已保存，主控已断开"):"记录停止："+error;
            if(!hostWanted&&wake.isHeld())wake.release();
            busy=lingering;if(lingering)phase+="；请关闭应用后重新打开";
            if(!hostWanted){stopForeground(true);stopSelf();}
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
        receivedLines=new ArrayBlockingQueue<String>(128);pending.reset();
        final CountDownLatch ready=new CountDownLatch(1);
        readerThread=new Thread(new Runnable(){public void run(){
            try{
                readerRequests=new UsbRequest[2];int consecutiveEmpty=0;
                for(int i=0;i<readerRequests.length;i++){
                    ByteBuffer buffer=ByteBuffer.allocateDirect(Math.max(64,input.getMaxPacketSize()));
                    UsbRequest request=new UsbRequest();readerRequests[i]=request;
                    if(!request.initialize(conn,input))throw new IOException("异步接收初始化失败");
                    request.setClientData(buffer);
                    if(!request.queue(buffer))throw new IOException("异步接收排队失败");
                }
                event("reader_armed","mode","UsbRequest_direct_queue_API26","buffers",2);ready.countDown();
                while(!cancelled){
                    // No timed requestWait: older Android libusbhost has short-timeout issues.
                    // Pending requests are cancelled by probe cleanup to end this wait.
                    UsbRequest response=conn.requestWait();
                    if(cancelled)break;
                    if(response==null)throw new IOException("USB异步等待失败");
                    ByteBuffer completed=(ByteBuffer)response.getClientData();int n=completed.position();
                    if(n<0||n>completed.capacity())throw new IOException("USB接收长度异常");
                    byte[] buffer=new byte[n];completed.flip();completed.get(buffer);
                    completed.clear();
                    boolean queued=response.queue(completed);
                    raw("RX",buffer,n);
                    if(!queued)throw new IOException("USB异步重新排队失败");
                    if(n==0){
                        /* Empty completion alone does not identify detach or failure.
                         * Preserve it, keep reception queued, and let the query deadline
                         * require an actual matching MCU reply. Never invent freshness. */
                        event("usb_empty_completion","consecutive",++consecutiveEmpty);
                        if(consecutiveEmpty>=32)throw new IOException("USB连续32次空完成，停止本轮；请检查连接");
                        continue;
                    }
                    consecutiveEmpty=0;
                    for(int j=0;j<n;j++){
                        if(buffer[j]=='\n'){
                            String rawLine=new String(pending.toByteArray(),StandardCharsets.US_ASCII);
                            String line=rawLine;pending.reset();
                            if(!receivedLines.offer(line))throw new IOException("回复队列满，记录不完整");
                        }else{
                            if(pending.size()>=4096)throw new IOException("回复超出上限，原始字节保留");pending.write(buffer[j]);
                        }
                    }
                }
            }catch(Exception error){if(!cancelled){readerError=error.toString();cancelled=true;try{event("reader_error","error",readerError);}catch(Exception ignored){}}}
            finally{UsbRequest[] requests=readerRequests;if(requests!=null)for(UsbRequest r:requests)if(r!=null){try{r.cancel();r.close();}catch(Exception ignored){}}}
        }},"board-usb-reader");readerThread.start();
        if(!ready.await(1000,TimeUnit.MILLISECONDS))throw new IOException("接收线程未启动");
        SystemClock.sleep(50);
    }
    private void cancelReader(){UsbRequest[] requests=readerRequests;if(requests!=null)for(UsbRequest r:requests)if(r!=null)try{r.cancel();}catch(Exception ignored){}}
    private void raw(String direction,byte[] bytes,int length)throws Exception{
        event("uart_bytes","direction",direction,"length",length,"data_b64",Base64.encodeToString(Arrays.copyOf(bytes,length),Base64.NO_WRAP));
    }

    private String query(UsbDeviceConnection conn,UsbEndpoint output,String command,String prefix)throws Exception{
        if(cancelled)throw new IOException("用户停止或USB断开");
        byte[] tx=(command+"\n").getBytes(StandardCharsets.US_ASCII);raw("TX_ATTEMPT",tx,tx.length);
        int sent=conn.bulkTransfer(output,tx,tx.length,1000);if(sent>0)raw("TX_ACCEPTED",tx,sent);
        if(sent!=tx.length)throw new IOException("发送不完整："+command);
        long deadline=SystemClock.elapsedRealtime()+3000;
        while(!cancelled&&SystemClock.elapsedRealtime()<deadline){
            if(journalError!=null||readerError!=null)throw new IOException(journalError!=null?journalError:readerError);
            String found=receivedLines.poll(100,TimeUnit.MILLISECONDS);
            if(found==null)continue;
            if(found.startsWith(prefix))return found;
            event("unexpected_reply","expected",prefix,"line",found);
        }
        if(journalError!=null||readerError!=null)throw new IOException(journalError!=null?journalError:readerError);
        throw new IOException(cancelled?"用户停止":"等待主控回复超时："+command);
    }

}
