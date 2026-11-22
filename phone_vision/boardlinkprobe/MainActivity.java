package cn.zhixing.boardlinkprobe;

import android.app.*;
import android.content.*;
import android.hardware.usb.*;
import android.os.*;
import android.util.Base64;
import android.widget.*;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.ByteBuffer;
import java.util.*;
import java.util.concurrent.*;

/** Restricted WCH-Link CDC probe. Only fixed read-only queries; no debug interface. */
public class MainActivity extends Activity {
    // USB interface ownership is process-wide, including old Activity instances.
    private static final Object PROBE_LOCK=new Object();
    private static MainActivity probeOwner;
    private static long processNextProbeAt;
    private static final String ACTION="cn.zhixing.boardlinkprobe.USB_PERMISSION";
    private static final String[] COMMANDS={"PING","STATUS","GIMBAL_STATUS","ULTRA_STATUS"};
    private static final String[] PREFIXES={"PONG","STATUS,","GIMBAL,","ULTRA,"};
    private static final String[] ECHO={"ZX_LOOP_A01","ZX_LOOP_B02","ZX_LOOP_C03"};
    private static final String[] NATIVE={"PING","NATIVE_ID","ZX_NATIVE_A01","ZX_NATIVE_B02","ZX_NATIVE_C03"};
    private static final String[] NATIVE_PREFIXES={"PONG","NATIVE_USBFS,","ZX_NATIVE_A01","ZX_NATIVE_B02","ZX_NATIVE_C03"};
    private UsbManager manager;
    private TextView view;
    private Button start,loopButton,nativeButton,telemetryButton;
    private boolean loopbackProbe=false,nativeProbe=false,telemetryProbe=false;
    private final Handler ui=new Handler();
    private volatile boolean cancelled=true,working=false;
    private volatile UsbDeviceConnection connection;
    private String info="等待连接主控",inventory="";
    private long eventSeq;
    private FileOutputStream journal;
    private final ByteArrayOutputStream pending=new ByteArrayOutputStream();
    private BlockingQueue<JSONObject> journalQueue;
    private BlockingQueue<String> receivedLines;
    private Thread journalThread,readerThread;
    private volatile boolean journalDone;
    private volatile String journalError,readerError;
    private volatile UsbRequest[] readerRequests;
    private long nextProbeAt;
    private boolean resumed=false,permissionPending=false;
    private UsbDevice permissionDevice,grantedDevice;
    private String permissionToken;
    private long permissionDeadline;
    private final String activityId=UUID.randomUUID().toString();
    // This small audit is separate from UART recording: it includes pre-USB failures.
    private synchronized void audit(String name,Object... pairs){
        try{
        JSONObject row=new JSONObject();row.put("event",name);row.put("app_version","0.10");
            row.put("elapsed_ns",SystemClock.elapsedRealtimeNanos());row.put("wall_ms",System.currentTimeMillis());
            row.put("activity_id",activityId);row.put("process_id",android.os.Process.myPid());
            for(int i=0;i<pairs.length;i+=2)row.put((String)pairs[i],pairs[i+1]);
            try(FileOutputStream out=new FileOutputStream(new File(getFilesDir(),"board-link-ui.jsonl"),true)){
                out.write((row.toString()+"\n").getBytes(StandardCharsets.UTF_8));out.getFD().sync();
            }
        }catch(Exception error){android.util.Log.e("BoardLinkProbe","UI audit failed",error);}
    }
    private final BroadcastReceiver receiver=new BroadcastReceiver(){
        public void onReceive(Context context,Intent intent){
            if(UsbManager.ACTION_USB_DEVICE_DETACHED.equals(intent.getAction())){
                UsbDevice d=intent.getParcelableExtra(UsbManager.EXTRA_DEVICE);
                if(isBoard(d)){audit("board_detached");clearPermission();cancelled=true;cancelReader();inventory();message("主控已拔下，停止自检");}
            }else if(UsbManager.ACTION_USB_DEVICE_ATTACHED.equals(intent.getAction())){
                UsbDevice d=intent.getParcelableExtra(UsbManager.EXTRA_DEVICE);
                if(isBoard(d)){audit("board_attached","device_name",d.getDeviceName());inventory();if(!working&&!permissionPending)message(d.getProductId()==0xfe0c?"已发现P7主控，请点上方开始按钮":"已发现WCH-Link，请选择对应自检");}
            }else if(ACTION.equals(intent.getAction())){
                UsbDevice d=intent.getParcelableExtra(UsbManager.EXTRA_DEVICE);
                // Old screens and stale broadcasts cannot start a probe.
                if(!permissionPending||permissionToken==null||!permissionToken.equals(intent.getStringExtra("probe_token"))||
                   !isBoard(d)||permissionDevice==null||!permissionDevice.getDeviceName().equals(d.getDeviceName())){
                    audit("permission_callback_ignored","pending",permissionPending,"token_matches",permissionToken!=null&&permissionToken.equals(intent.getStringExtra("probe_token")));return;
                }
                audit("permission_callback","granted",intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED,false),"actual_permission",manager.hasPermission(d));
                permissionPending=false;permissionDevice=null;permissionToken=null;
                if(intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED,false)&&manager.hasPermission(d)){
                    grantedDevice=d;consumeGrant();
                }else message("主控访问权限未允许");
            }
        }
    };
    private boolean isBoard(UsbDevice d){return d!=null&&d.getVendorId()==0x1a86&&(d.getProductId()==0x8010||d.getProductId()==0xfe0c);}
    public void onCreate(Bundle state){
        super.onCreate(state);manager=(UsbManager)getSystemService(USB_SERVICE);
        ScrollView page=new ScrollView(this);page.setFillViewport(true);
        LinearLayout box=new LinearLayout(this);box.setOrientation(1);box.setPadding(16,12,16,16);page.addView(box);
        TextView title=new TextView(this);title.setText("知行回路 · 通信自检 v0.10");title.setTextSize(18);box.addView(title);
        telemetryButton=new Button(this);telemetryButton.setId(0x1001);telemetryButton.setText("开始P7通信自检（12次）");box.addView(telemetryButton);
        telemetryButton.setOnClickListener(new android.view.View.OnClickListener(){public void onClick(android.view.View v){request(false,true,true);}});
        view=new TextView(this);view.setId(0x1002);view.setTextSize(16);view.setPadding(8,8,8,12);
        view.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);box.addView(view);
        LinearLayout actions=new LinearLayout(this);actions.setOrientation(0);box.addView(actions);
        Button stop=new Button(this);stop.setText("停止");actions.addView(stop,new LinearLayout.LayoutParams(0,-2,1));
        stop.setOnClickListener(new android.view.View.OnClickListener(){public void onClick(android.view.View v){clearPermission();cancelled=true;cancelReader();audit("stop_clicked");message("已请求停止，等待本轮关闭");}});
        Button refresh=new Button(this);refresh.setText("重新识别");actions.addView(refresh,new LinearLayout.LayoutParams(0,-2,1));
        refresh.setOnClickListener(new android.view.View.OnClickListener(){public void onClick(android.view.View v){audit("refresh_clicked");inventory();message("USB设备列表已刷新\n"+inventorySummary());}});
        TextView hint=new TextView(this);hint.setText("接法：小手机 → OTG → 开发板P7\nP9不接；电机、舵机电源保持断开。\n查询和原始回复记录在本手机。");hint.setTextSize(14);box.addView(hint);
        final LinearLayout advanced=new LinearLayout(this);advanced.setOrientation(1);advanced.setVisibility(android.view.View.GONE);
        final Button expand=new Button(this);expand.setText("展开其他诊断");box.addView(expand);box.addView(advanced);
        expand.setOnClickListener(new android.view.View.OnClickListener(){public void onClick(android.view.View v){boolean show=advanced.getVisibility()!=android.view.View.VISIBLE;advanced.setVisibility(show?android.view.View.VISIBLE:android.view.View.GONE);expand.setText(show?"收起其他诊断":"展开其他诊断");}});
        start=new Button(this);start.setText("P9主控通信自检（原跳帽）");advanced.addView(start);start.setOnClickListener(new android.view.View.OnClickListener(){public void onClick(android.view.View v){request(false);}});
        loopButton=new Button(this);loopButton.setText("WCH回环测试（须改J2）");advanced.addView(loopButton);loopButton.setOnClickListener(new android.view.View.OnClickListener(){public void onClick(android.view.View v){request(true);}});
        nativeButton=new Button(this);nativeButton.setText("P7固定回声诊断（5次）");advanced.addView(nativeButton);nativeButton.setOnClickListener(new android.view.View.OnClickListener(){public void onClick(android.view.View v){request(false,true);}});
        setContentView(page);
        IntentFilter filter=new IntentFilter(ACTION);filter.addAction(UsbManager.ACTION_USB_DEVICE_DETACHED);filter.addAction(UsbManager.ACTION_USB_DEVICE_ATTACHED);registerReceiver(receiver,filter);
        // Real Android matching check; no USB permission or device response is simulated.
        int oldMatch=filter.matchData(null,"zhixing-probe",android.net.Uri.parse("zhixing-probe://permission/check"));
        int fixedMatch=filter.matchData(null,null,null);
        audit("permission_filter_check","old_uri_match",oldMatch,"fixed_no_data_match",fixedMatch,"passed",oldMatch<0&&fixedMatch>=0);
        inventory();
    }
    private void inventory(){
        StringBuilder text=new StringBuilder();boolean found=false;
        for(UsbDevice d:manager.getDeviceList().values()){
            text.append(String.format(Locale.US,"%04X:%04X",d.getVendorId(),d.getProductId())).append(isBoard(d)?(d.getProductId()==0xfe0c?" 已匹配USBFS测试设备\n":" 已匹配WCH-Link\n"):" 非本次目标\n");
            if(isBoard(d))found=true;
            for(int i=0;i<d.getInterfaceCount();i++){
                UsbInterface f=d.getInterface(i);text.append("接口 ").append(f.getId()).append(" 类别 ").append(f.getInterfaceClass()).append(" 子类 ").append(f.getInterfaceSubclass()).append("\n");
            }
        }
        inventory=found?text.toString():"未发现WCH-Link(1A86:8010)或USBFS测试设备(1A86:FE0C)。\n"+text;
        audit("inventory","board_found",found);
        message(info);
    }
    private String inventorySummary(){return manager.getDeviceList().isEmpty()?"当前USB设备列表为空，尚未识别开发板":"已列出USB设备，请看状态区的标识";}
    private void message(String value){info=value;ui.post(new Runnable(){public void run(){view.setText(info+"\n\n"+inventory);boolean available=!working&&!permissionPending&&grantedDevice==null;start.setEnabled(available);loopButton.setEnabled(available);nativeButton.setEnabled(available);telemetryButton.setEnabled(true);}});}
    private void clearPermission(){permissionPending=false;permissionDevice=null;grantedDevice=null;permissionToken=null;}
    private void consumeGrant(){if(resumed&&grantedDevice!=null){UsbDevice d=grantedDevice;grantedDevice=null;launch(d);}}
    private void watchPermission(final String token){ui.postDelayed(new Runnable(){public void run(){
        if(!permissionPending||!token.equals(permissionToken))return;
        UsbDevice live=permissionDevice==null?null:manager.getDeviceList().get(permissionDevice.getDeviceName());
        if(!isBoard(live)){audit("permission_device_gone");clearPermission();inventory();message("等待授权时USB设备已断开；本轮停止");return;}
        if(manager.hasPermission(live)){
            audit("permission_confirmed","source","hasPermission_poll");clearPermission();grantedDevice=live;consumeGrant();return;
        }
        if(SystemClock.elapsedRealtime()>=permissionDeadline){
            audit("permission_timeout","seconds",20,"board_still_present",true,"resumed",resumed);
            clearPermission();inventory();message("20秒内未完成USB授权，本轮已停止。\n若没有系统弹窗，请将手机接回电脑读取授权记录；不要连续重试。");return;
        }
        watchPermission(token);
    }},500);}
    private void request(boolean loopback){request(loopback,false);}
    private void request(boolean loopback,boolean useNative){request(loopback,useNative,false);}
    private void request(boolean loopback,boolean useNative,boolean telemetry){
        Toast.makeText(this,"已点击，正在检查连接",Toast.LENGTH_SHORT).show();
        audit("start_clicked","resumed",resumed,"working",working,"permission_pending",permissionPending,"grant_pending",grantedDevice!=null,"mode",telemetry?"NATIVE_TELEMETRY":useNative?"NATIVE_USBFS":loopback?"WCH_LOOPBACK":"READ_ONLY");
        if(!resumed){message("页面尚未回到前台，请先关闭系统弹窗再点开始");return;}
        if(working){message("自检正在运行，请等待结果；需要中止可点停止");return;}
        if(permissionPending){message("正在等待安卓USB授权，20秒后会自动结束；无需再次点击");return;}
        if(grantedDevice!=null){message("USB已授权，正在等待启动本轮自检");return;}
        if(SystemClock.elapsedRealtime()<nextProbeAt){message("上一轮已结束，稍等两秒再开始");return;}
        loopbackProbe=loopback;nativeProbe=useNative;telemetryProbe=telemetry;
        inventory();
        for(UsbDevice d:manager.getDeviceList().values())if(isBoard(d)&&d.getProductId()==(nativeProbe?0xfe0c:0x8010)){
            audit("probe_requested","device_name",d.getDeviceName(),"permission_already_granted",manager.hasPermission(d),"mode",telemetryProbe?"NATIVE_TELEMETRY":nativeProbe?"NATIVE_USBFS":loopbackProbe?"WCH_LOOPBACK":"READ_ONLY");
            if(manager.hasPermission(d))launch(d);
            else {
                permissionPending=true;permissionDevice=d;permissionToken=UUID.randomUUID().toString();
                permissionDeadline=SystemClock.elapsedRealtime()+20000;
                // No data URI: the receiver has an action-only filter. Unique token
                // still rejects obsolete grants; CANCEL_CURRENT replaces the old intent.
                Intent permission=new Intent(ACTION).setPackage(getPackageName()).putExtra("probe_token",permissionToken);
                message("已发现目标设备，正在申请USB授权。\n请在安卓系统弹窗点允许／确定，不用再点开始。\n20秒未完成会自动停止。");
                audit("permission_requested");
                try{manager.requestPermission(d,PendingIntent.getBroadcast(this,0,permission,PendingIntent.FLAG_ONE_SHOT|PendingIntent.FLAG_CANCEL_CURRENT));watchPermission(permissionToken);}
                catch(Exception error){audit("permission_request_error","error",error.toString());clearPermission();message("申请权限失败："+error.getMessage());}
            }
            return;
        }
        inventory();audit("start_no_target","native",nativeProbe,"usb_device_count",manager.getDeviceList().size());
        message(nativeProbe?"未识别到P7主控（1A86:FE0C）\n"+inventorySummary()+"\n本轮没有发送查询。请保持接线，保留此提示。":"未识别到P9 WCH-Link，请核对OTG与P9插头");
    }
    private synchronized void event(String name,Object... pairs)throws Exception{
        JSONObject row=new JSONObject();row.put("seq",++eventSeq);row.put("elapsed_ns",SystemClock.elapsedRealtimeNanos());row.put("wall_ms",System.currentTimeMillis());row.put("event",name);
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
                    if(row!=null)journal.write((row.toString()+"\n").getBytes(StandardCharsets.UTF_8));
                    if(SystemClock.elapsedRealtime()-synced>=1000){journal.flush();journal.getFD().sync();synced=SystemClock.elapsedRealtime();}
                }
                journal.flush();journal.getFD().sync();
            }catch(Exception error){journalError=error.toString();cancelled=true;}
            finally{try{journal.close();}catch(IOException error){journalError=error.toString();}}
        }},"board-log-writer");journalThread.start();
    }
    private void startReader(final UsbDeviceConnection conn,final UsbEndpoint input)throws Exception{
        receivedLines=new ArrayBlockingQueue<String>(128);pending.reset();
        final CountDownLatch ready=new CountDownLatch(1);
        readerThread=new Thread(new Runnable(){public void run(){
            try{
                readerRequests=new UsbRequest[2];
                for(int i=0;i<readerRequests.length;i++){
                    ByteBuffer buffer=ByteBuffer.allocate(Math.max(64,input.getMaxPacketSize()));
                    UsbRequest request=new UsbRequest();readerRequests[i]=request;
                    if(!request.initialize(conn,input))throw new IOException("异步接收初始化失败");
                    request.setClientData(buffer);
                    if(!request.queue(buffer,buffer.capacity()))throw new IOException("异步接收排队失败");
                }
                event("reader_armed","mode","UsbRequest","buffers",2);ready.countDown();
                while(!cancelled){
                    // No timed requestWait: older Android libusbhost has short-timeout issues.
                    // Pending requests are cancelled by probe cleanup to end this wait.
                    UsbRequest response=conn.requestWait();
                    if(cancelled)break;
                    if(response==null)throw new IOException("USB异步等待失败");
                    ByteBuffer completed=(ByteBuffer)response.getClientData();int n=completed.position();
                    if(n<=0)throw new IOException("USB异步接收空数据，连接可能中断");
                    byte[] buffer=Arrays.copyOf(completed.array(),n);
                    completed.clear();
                    boolean queued=response.queue(completed,completed.capacity());
                    raw("RX",buffer,n);
                    if(!queued)throw new IOException("USB异步重新排队失败");
                    for(int j=0;j<n;j++){
                        if(buffer[j]=='\n'){
                            String rawLine=new String(pending.toByteArray(),StandardCharsets.US_ASCII);
                            String line=loopbackProbe||nativeProbe?rawLine:rawLine.trim();pending.reset();
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
    private void launch(final UsbDevice device){
        if(!resumed||working)return;
        if(readerThread!=null&&readerThread.isAlive()){message("旧接收尚未关闭，请退出程序后重开");return;}
        synchronized(PROBE_LOCK){
            if(probeOwner!=null){message("另一轮自检尚未关闭，请等它结束");return;}
            if(SystemClock.elapsedRealtime()<processNextProbeAt){message("上一轮已结束，稍等两秒再开始");return;}
            probeOwner=this;working=true;cancelled=false;
        }
        message(telemetryProbe?"正在设置USBFS，查询正常功能状态12次":nativeProbe?"正在设置USBFS串口，随后查询5次（独立诊断固件）":loopbackProbe?"正在设置串口，随后测试3组原样回声；不是主控自检":"正在设置串口；完成后查询12次，出错会提前结束");
        final boolean echoMode=loopbackProbe;
        final boolean nativeMode=nativeProbe;
        final boolean telemetryMode=telemetryProbe;
        try{new Thread(new Runnable(){public void run(){
            try{probe(device,echoMode,nativeMode,telemetryMode);}finally{synchronized(PROBE_LOCK){
                // A stuck reader keeps the lock until the process is restarted.
                if(probeOwner==MainActivity.this&&(readerThread==null||!readerThread.isAlive())&&
                   (journalThread==null||!journalThread.isAlive())){
                    processNextProbeAt=SystemClock.elapsedRealtime()+2000;probeOwner=null;
                }
            }}
        }},"board-link-probe").start();}
        catch(RuntimeException error){synchronized(PROBE_LOCK){probeOwner=null;working=false;cancelled=true;}message("无法启动自检："+error.getMessage());}
    }
    private void probe(UsbDevice device,boolean echoMode,boolean nativeMode,boolean telemetryMode){
        UsbInterface control=null,data=null;UsbEndpoint input=null,output=null;
        String result="自检未完成";int pass=0;boolean complete=false;File folder=null;
        final String mode=telemetryMode?"NATIVE_TELEMETRY":nativeMode?"NATIVE_USBFS":echoMode?"WCH_LOOPBACK":"READ_ONLY";
        final String[] commands=telemetryMode?COMMANDS:nativeMode?NATIVE:echoMode?ECHO:COMMANDS;
        final String[] prefixes=telemetryMode?PREFIXES:nativeMode?NATIVE_PREFIXES:echoMode?ECHO:PREFIXES;
        final int rounds=telemetryMode?3:nativeMode||echoMode?1:3,total=telemetryMode?12:nativeMode?5:echoMode?3:12;
        long previousUptime=-1;
        journal=null;journalThread=null;readerThread=null;readerRequests=null;journalError=null;readerError=null;
        try{
            folder=new File(getFilesDir(),"board-link/"+System.currentTimeMillis());if(!folder.mkdirs())throw new IOException("无法创建日志目录");
            startJournal(folder);
            event("session_started","vid_pid",nativeMode?"1A86:FE0C":"1A86:8010","baud",115200,"app_version","0.10","mode",mode,"expected_replies",total,"clock","Android elapsedRealtimeNanos","rx_mode","UsbRequest_two_buffers_before_tx","log_mode","independent_writer_fsync_1s","activity_id",activityId,"process_id",android.os.Process.myPid(),"single_probe_owner",true);
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
                message("串口设置失败，正在进行一次USB重新配置恢复");
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
            if(got==7&&!Arrays.equals(line,actual))throw new IOException("串口参数读回不一致");
            int handshake=conn.controlTransfer(0x21,0x22,3,control.getId(),null,0,1000);event("cdc_control_lines","result",handshake);if(handshake<0)throw new IOException("串口控制设置失败");
            startReader(conn,input);SystemClock.sleep(250);
            if(telemetryMode){
                String identity=query(conn,output,"NATIVE_FEATURES","NORMAL_USBFS,");
                if(!identity.equals("NORMAL_USBFS,1"))throw new IOException("USBFS正常功能固件标识不符");
                event("native_features_verified","line",identity);
            }
            for(int round=0;round<rounds&&!cancelled;round++){
                for(int i=0;i<commands.length&&!cancelled;i++){
                    message((echoMode?"回环测试 ":"正在查询 ")+commands[i]+" · "+pass+"/"+total);
                    String response=query(conn,output,commands[i],prefixes[i]);
                    event("received_reply","command",commands[i],"line",response);
                    if(nativeMode&&!telemetryMode){String exact=i==0?"PONG":i==1?"NATIVE_USBFS,1":commands[i];if(!response.equals(exact))throw new IOException("USBFS诊断回复不符");}
                    else if(echoMode){if(!response.equals(commands[i]))throw new IOException("回环返回字节内容不一致");}else validate(i,response);
                    if(telemetryMode&&i==1){
                        long uptime=Long.parseLong(response.split(",",-1)[1]);
                        if(previousUptime>=0&&uptime<=previousUptime)throw new IOException("主控运行时间没有继续增加");
                        previousUptime=uptime;
                    }
                    pass++;
                    event("query_reply","command",commands[i],"line",response,"round",round+1);
                    message((echoMode?"WCH原样回声 ":"主控回复 ")+pass+"/"+total+"\n"+response);
                }
                SystemClock.sleep(250);
            }
            result=pass==total?(telemetryMode?"USBFS正常功能通信通过12/12\n运行时间持续增加，原始收发已保存在手机":nativeMode?"USBFS主控直连通过5/5（独立诊断固件）\n原始收发已保存在手机":echoMode?"WCH回环通过3/3（不是主控通信通过）\n原始收发已保存在手机":"通信通过：主控连续回复12/12\n原始收发已保存在手机"):cancelled?"已停止；本轮未完整完成":"本轮未完整完成";
            if(journalError!=null||readerError!=null)throw new IOException(journalError!=null?journalError:readerError);
            event("session_finished","passed",pass==total,"replies",pass,"cancelled",cancelled,"mode",mode);
            complete=pass==total;
        }catch(Exception error){result="未通过："+error.getMessage()+"\n请保留接线状态，接回电脑读取日志";try{if(journal!=null)event("session_error","error",error.toString(),"replies",pass);}catch(Exception ignored){result+="\n日志写入也失败，记录不完整";}}
        finally{
            cancelled=true;UsbDeviceConnection conn=connection;connection=null;
            cancelReader();
            try{if(readerThread!=null)readerThread.join(500);}catch(InterruptedException ignored){}
            if(conn!=null){try{if(data!=null)conn.releaseInterface(data);if(control!=null)conn.releaseInterface(control);}finally{conn.close();}}
            try{if(readerThread!=null&&readerThread.isAlive())readerThread.join(1000);}catch(InterruptedException ignored){}
            journalDone=true;try{if(journalThread!=null)journalThread.join(3000);}catch(InterruptedException ignored){}
            if(journalError!=null||(journalThread!=null&&journalThread.isAlive())||(readerThread!=null&&readerThread.isAlive())){complete=false;result+="\n日志/接收未正常结束，记录不完整";}
            if(folder!=null)try{JSONObject meta=new JSONObject();meta.put("result",result);meta.put("replies",pass);meta.put("passed",complete);meta.put("mode",mode);meta.put("expected_replies",total);try(FileOutputStream f=new FileOutputStream(new File(folder,"result.json"))){f.write(meta.toString().getBytes(StandardCharsets.UTF_8));f.getFD().sync();}}catch(Exception ignored){result+="\n汇总保存失败，记录不完整";}
            nextProbeAt=SystemClock.elapsedRealtime()+2000;working=false;message(result);
        }
    }
    private String query(UsbDeviceConnection conn,UsbEndpoint output,String command,String prefix)throws Exception{
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
        throw new IOException(cancelled?"用户停止":command.startsWith("ZX_LOOP_")?"等待WCH回环返回超时："+command:"等待主控回复超时："+command);
    }
    private void validate(int i,String line)throws Exception{
        if(i==0){if(!line.equals("PONG"))throw new IOException("PING回复格式不符");return;}
        String[] fields=line.split(",",-1);int expected=i==1?12:i==2?11:13;
        if(fields.length!=expected)throw new IOException("状态字段数不符："+fields[0]+" 收到"+(fields.length-1)+"，预期"+(expected-1));
        for(int k=1;k<fields.length;k++)Long.parseLong(fields[k]);
    }
    public void onResume(){super.onResume();resumed=true;consumeGrant();}
    public void onPause(){resumed=false;cancelled=true;cancelReader();super.onPause();}
    public void onDestroy(){resumed=false;clearPermission();cancelled=true;cancelReader();unregisterReceiver(receiver);super.onDestroy();}
}
