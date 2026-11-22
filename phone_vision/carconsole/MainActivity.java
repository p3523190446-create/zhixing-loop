package cn.zhixing.carconsole;

import android.app.*;
import android.content.*;
import android.hardware.usb.*;
import android.os.*;
import android.widget.*;
import java.util.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import org.json.*;
import android.webkit.*;

/** Visible UI; only the foreground service owns USB and records bytes. */
public class MainActivity extends Activity {
    private static final String PERMISSION="cn.zhixing.carconsole.USB_PERMISSION";
    private UsbManager usb;private TelemetryService service;
    private boolean bound,permissionPending;private String permissionToken;private UsbDevice pendingDevice;
    private long permissionUntil;private Handler handler=new Handler();
    private ScrollView nativePage;private WebView browser;private boolean webShowing;
    private TextView webStatusLine;
    private TextView status,range,ultra,uptime,system,record;private String notice="请连接小手机 → OTG → 开发板P7";
    private final ServiceConnection binding=new ServiceConnection(){
        public void onServiceConnected(ComponentName n,IBinder b){service=((TelemetryService.LocalBinder)b).getService();service.noteVisibility(true);render();}
        public void onServiceDisconnected(ComponentName n){service=null;render();}
    };
    private final BroadcastReceiver permissions=new BroadcastReceiver(){
        public void onReceive(Context c,Intent i){
            UsbDevice d=i.getParcelableExtra(UsbManager.EXTRA_DEVICE);
            if(!permissionPending||!permissionToken.equals(i.getStringExtra("token"))||d==null||pendingDevice==null||!d.getDeviceName().equals(pendingDevice.getDeviceName()))return;
            audit("usb_permission_callback","granted",i.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED,false),"actual_permission",usb.hasPermission(d));
            permissionPending=false;pendingDevice=null;permissionToken=null;
            if(i.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED,false)&&usb.hasPermission(d))launch(d);
            else {notice="USB访问未允许，请点开始重新申请";render();}
        }
    };
    public void onCreate(Bundle saved){
        super.onCreate(saved);usb=(UsbManager)getSystemService(USB_SERVICE);
        ScrollView scroll=new ScrollView(this);nativePage=scroll;LinearLayout box=new LinearLayout(this);box.setOrientation(1);box.setPadding(16,12,16,20);scroll.addView(box);
        TextView title=label(box,"知行回路 · 车载端 0.3",20);
        Button webButton=new Button(this);webButton.setText("打开调试台网页");box.addView(webButton);webButton.setOnClickListener(new android.view.View.OnClickListener(){public void onClick(android.view.View v){openWeb();}});
        Button start=new Button(this);start.setText("连接主控并开始记录");box.addView(start);start.setOnClickListener(new android.view.View.OnClickListener(){public void onClick(android.view.View v){request();}});
        status=label(box,notice,16);range=label(box,"前方距离  —",25);ultra=label(box,"超声距离  —",20);uptime=label(box,"主控运行  —",18);
        system=label(box,"预警 / 声音 / 屏幕状态待连接",16);
        record=label(box,"记录未开始",14);
        Button stop=new Button(this);stop.setText("停止记录并断开");box.addView(stop);stop.setOnClickListener(new android.view.View.OnClickListener(){public void onClick(android.view.View v){audit("stop_clicked");if(service!=null)service.requestStop("USER_STOP");notice="已请求停止，正在保存记录";render();}});
        TextView tip=label(box,"这一版读取真实状态并持续记录。\n接P7，P9留空；本轮电机和舵机保持断电。\n退出到桌面仍可记录，通知栏可停止。\n日志在手机本地；退出页面不会删除记录。",14);
        setContentView(scroll);registerReceiver(permissions,new IntentFilter(PERMISSION));
        audit("app_open","version","0.3");
    }
    private TextView label(LinearLayout b,String text,int size){TextView v=new TextView(this);v.setText(text);v.setTextSize(size);v.setPadding(6,8,6,8);b.addView(v);return v;}
    private void openWeb(){
        if(service==null||service.webUrl()==null){notice="网页服务尚未就绪，请稍后再试";render();return;}
        service.startHost();final String root=service.webUrl().replace("/mobile","");
        LinearLayout box=new LinearLayout(this);box.setOrientation(1);LinearLayout bar=new LinearLayout(this);bar.setOrientation(0);box.addView(bar);
        Button connect=new Button(this);connect.setText("连接主控");bar.addView(connect,new LinearLayout.LayoutParams(0,-2,1));connect.setOnClickListener(new android.view.View.OnClickListener(){public void onClick(android.view.View v){request();}});
        Button back=new Button(this);back.setText("连接与地址");bar.addView(back,new LinearLayout.LayoutParams(0,-2,1));back.setOnClickListener(new android.view.View.OnClickListener(){public void onClick(android.view.View v){showNative();}});
        webStatusLine=label(box,"正在打开车载网页",14);
        browser=new WebView(this);browser.getSettings().setJavaScriptEnabled(true);browser.getSettings().setDomStorageEnabled(true);browser.getSettings().setAllowFileAccess(false);browser.getSettings().setAllowContentAccess(false);browser.getSettings().setSupportZoom(true);
        browser.setWebViewClient(new WebViewClient(){public boolean shouldOverrideUrlLoading(WebView view,String url){return !url.startsWith(root+"/");}});
        browser.setWebChromeClient(new WebChromeClient(){public boolean onConsoleMessage(ConsoleMessage m){android.util.Log.i("CarWebConsole",m.message()+" @ "+m.lineNumber());return true;}});
        WebView.setWebContentsDebuggingEnabled(true);box.addView(browser,new LinearLayout.LayoutParams(-1,0,1));webShowing=true;setContentView(box);browser.loadUrl(service.webUrl()+"#telemetry");audit("web_open");
    }
    private void showNative(){if(browser!=null){browser.destroy();browser=null;}webShowing=false;setContentView(nativePage);render();}
    private boolean target(UsbDevice d){return d!=null&&d.getVendorId()==0x1a86&&d.getProductId()==0xfe0c;}
    private synchronized void audit(String name,Object... pairs){try{
        JSONObject row=new JSONObject();row.put("event",name);row.put("elapsed_ns",SystemClock.elapsedRealtimeNanos());row.put("wall_ms",System.currentTimeMillis());row.put("version","0.3");
        for(int k=0;k<pairs.length;k+=2)row.put((String)pairs[k],pairs[k+1]);
        try(FileOutputStream f=new FileOutputStream(new File(getFilesDir(),"ui-events.jsonl"),true)){f.write((row.toString()+"\n").getBytes(StandardCharsets.UTF_8));f.getFD().sync();}
    }catch(Exception e){notice="界面记录写入失败："+e.getMessage();android.util.Log.e("CarConsole","UI journal failed",e);}}
    private void request(){
        Toast.makeText(this,"已点击，正在检查主控",Toast.LENGTH_SHORT).show();
        audit("start_clicked","service_ready",service!=null,"busy",service!=null&&service.isBusy(),"permission_pending",permissionPending);
        if(service==null){notice="记录服务尚未就绪，请稍等";render();return;}
        if(service.isBusy()){notice="正在记录；停止请点下方停止按钮";render();return;}
        if(permissionPending){notice="正在等待系统USB授权，无需重复点击";render();return;}
        UsbDevice found=null;int count=0;for(UsbDevice d:usb.getDeviceList().values())if(target(d)){found=d;count++;}
        audit("usb_inventory","device_count",usb.getDeviceList().size(),"target_count",count);
        if(count!=1){notice=count==0?"未识别到P7主控，尚未发送查询":"发现多个P7主控，本轮不连接";render();return;}
        if(usb.hasPermission(found)){launch(found);return;}
        permissionPending=true;pendingDevice=found;permissionToken=UUID.randomUUID().toString();permissionUntil=SystemClock.elapsedRealtime()+20000;
        notice="请在安卓USB访问弹窗点允许";render();
        audit("usb_permission_requested");
        Intent intent=new Intent(PERMISSION).setPackage(getPackageName()).putExtra("token",permissionToken);
        try{usb.requestPermission(found,PendingIntent.getBroadcast(this,0,intent,PendingIntent.FLAG_ONE_SHOT|PendingIntent.FLAG_CANCEL_CURRENT));watchPermission(permissionToken);}
        catch(Exception e){permissionPending=false;notice="申请权限失败："+e.getMessage();audit("usb_permission_error","error",e.toString());render();}
    }
    private void watchPermission(final String token){handler.postDelayed(new Runnable(){public void run(){
        if(!permissionPending||!token.equals(permissionToken))return;
        UsbDevice d=pendingDevice==null?null:usb.getDeviceList().get(pendingDevice.getDeviceName());
        if(!target(d)){permissionPending=false;notice="等待授权时USB已断开";audit("usb_permission_device_gone");render();return;}
        if(usb.hasPermission(d)){permissionPending=false;pendingDevice=null;permissionToken=null;launch(d);return;}
        if(SystemClock.elapsedRealtime()>=permissionUntil){permissionPending=false;notice="20秒授权超时，本轮停止";audit("usb_permission_timeout");render();return;}
        watchPermission(token);
    }},500);}
    private void launch(UsbDevice d){notice="正在连接并创建记录";render();Intent i=new Intent(this,TelemetryService.class).setAction(TelemetryService.START).putExtra("device",d);startForegroundService(i);}
    private final Runnable refresh=new Runnable(){public void run(){render();handler.postDelayed(this,500);}};
    private void render(){
        if(status==null)return;
        if(service==null){show(status,notice);return;}
        Map<String,String> data=service.snapshot();long age=service.sampleAge();boolean fresh=service.isBusy()&&age>=0&&age<2500;
        String idleNote=notice.startsWith("正在连接")||notice.startsWith("已请求停止")?"点击连接可开始一段新记录":notice;
        show(status,service.isBusy()?service.phase()+" · "+(fresh?"数据实时更新":"等待新数据"):service.phase()+"\n"+idleNote);
        if(webShowing&&webStatusLine!=null)show(webStatusLine,status.getText());
        long[] tof=numbers(data.get("STATUS")),us=numbers(data.get("ULTRA_STATUS")),param=numbers(data.get("PARAM_STATUS")),mute=numbers(data.get("MUTE_STATUS")),gimbal=numbers(data.get("GIMBAL_STATUS")),motor=numbers(data.get("MOTOR_DASH_STATUS"));
        show(range,"前方距离  "+(fresh&&tof!=null&&tof[2]==0&&tof[3]==0&&tof[4]!=4294967295L?cm(tof[4]):"—"));
        show(ultra,"超声距离  "+(fresh&&us!=null&&us[1]==1&&us[2]==1?cm(us[3]):"—"));
        show(uptime,"主控运行  "+(fresh&&tof!=null?tof[0]/1000+" 秒":"—"));
        StringBuilder info=new StringBuilder();
        if(!fresh)info.append("当前数据已失效，等待重新连接\n");
        else {
            info.append("预警距离：").append(param!=null?cm(param[0]):"—").append("\n声音：").append(mute!=null?(mute[0]==1?"静音":"开启"):"—");
            info.append("\n云台：").append(gimbal!=null?(gimbal[2]==0?"未启动":"运行中"):"—");
            info.append("\n电机板：").append(motor!=null&&motor[2]==1?"电压 "+motor[1]/1000.0+" V":"未收到新鲜反馈");
            info.append("\n屏幕：");for(String c:new String[]{"OLED_SCREEN","OLED2_SCREEN","OLED3_SCREEN"}){long[] v=numbers(data.get(c));info.append(v!=null&&v[1]==1&&v[2]==0?"正常 ":"待检查 ");}
        }
        show(system,info);String addresses=service.webUrls().toString();show(record,"记录编号："+service.session()+"\n已查询 "+service.replyCount()+" 次 · 已落盘 "+service.persistedCount()+" 条\n"+service.logState()+"\n主力手机网页地址：\n"+addresses);
    }
    private void show(TextView v,CharSequence text){String s=text.toString();if(!v.getText().toString().equals(s))v.setText(s);}
    private long[] numbers(String line){if(line==null)return null;try{String[] f=line.split(",",-1);long[] n=new long[f.length-1];for(int k=1;k<f.length;k++)n[k-1]=Long.parseLong(f[k]);return n;}catch(Exception e){return null;}}
    private String cm(long mm){return String.format(Locale.CHINA,"%.1f 厘米",mm/10.0);}
    public void onStart(){super.onStart();audit("ui_visible","visible",true);bound=bindService(new Intent(this,TelemetryService.class),binding,BIND_AUTO_CREATE);handler.post(refresh);}
    public void onStop(){audit("ui_visible","visible",false);handler.removeCallbacks(refresh);if(service!=null)service.noteVisibility(false);if(bound){unbindService(binding);bound=false;service=null;}super.onStop();}
    public void onBackPressed(){if(webShowing){showNative();return;}super.onBackPressed();}
    public void onDestroy(){if(browser!=null)browser.destroy();unregisterReceiver(permissions);handler.removeCallbacksAndMessages(null);super.onDestroy();}
}
