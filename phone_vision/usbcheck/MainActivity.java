package cn.zhixing.usbcheck;
import android.app.Activity;
import android.app.PendingIntent;
import android.content.*;
import android.content.pm.PackageManager;
import android.hardware.usb.*;
import android.os.*;
import android.util.Log;
import android.widget.*;
import org.json.*;
import java.util.*;

public class MainActivity extends Activity {
    private UsbManager usb;
    private TextView report;
    private final Handler handler=new Handler();
    private boolean running;
    private String permissionResult="尚未申请设备访问权限";
    private String lastLog="";
    private static final String ACTION="cn.zhixing.usbcheck.USB_PERMISSION";
    private final BroadcastReceiver receiver=new BroadcastReceiver(){
        public void onReceive(Context context,Intent intent){
            permissionResult=intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED,false)?"设备访问权限已允许":"设备访问权限未允许";
            refresh();
        }
    };
    private final Runnable poll=new Runnable(){public void run(){if(running){refresh();handler.postDelayed(this,1000);}}};
    public void onCreate(Bundle state){
        super.onCreate(state);usb=(UsbManager)getSystemService(USB_SERVICE);
        LinearLayout box=new LinearLayout(this);box.setOrientation(1);box.setPadding(20,20,20,20);
        TextView title=new TextView(this);title.setText("知行回路 · USB设备自检");title.setTextSize(21);box.addView(title);
        TextView hint=new TextView(this);hint.setText("本页只检查USB识别和访问权限。\n不显示相机画面，不控制电机。\n安装完成后：手机 → OTG → 摄像头原配USB线。");box.addView(hint);
        Button request=new Button(this);request.setText("申请摄像头访问权限");box.addView(request);
        request.setOnClickListener(new android.view.View.OnClickListener(){public void onClick(android.view.View view){
            UsbDevice selected=null;
            for(UsbDevice d:devices())if(d.getVendorId()==0x145f && d.getProductId()==0x02ec){selected=d;break;}
            if(selected==null){permissionResult="未找到电脑识别的145F:02EC摄像头；不申请其他设备权限";refresh();return;}
            if(usb.hasPermission(selected)){permissionResult="摄像头访问权限已允许";refresh();return;}
            usb.requestPermission(selected,PendingIntent.getBroadcast(MainActivity.this,0,new Intent(ACTION).setPackage(getPackageName()),0));
        }});
        report=new TextView(this);report.setTextSize(15);ScrollView scroll=new ScrollView(this);scroll.addView(report);box.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));setContentView(box);
        registerReceiver(receiver,new IntentFilter(ACTION));
    }
    private List<UsbDevice> devices(){List<UsbDevice> list=new ArrayList<>(usb.getDeviceList().values());Collections.sort(list,new Comparator<UsbDevice>(){public int compare(UsbDevice a,UsbDevice b){return Integer.compare(a.getDeviceId(),b.getDeviceId());}});return list;}
    private void refresh(){
        boolean host=getPackageManager().hasSystemFeature(PackageManager.FEATURE_USB_HOST);
        List<UsbDevice> list=devices();StringBuilder text=new StringBuilder("系统声明USB Host："+(host?"有":"无")+"\n当前USB设备："+list.size()+"\n"+permissionResult+"\n\n");
        JSONObject data=new JSONObject();JSONArray entries=new JSONArray();
        try{
            data.put("elapsed_ms",SystemClock.elapsedRealtime());data.put("host_feature",host);
            for(UsbDevice d:list){
                String id=String.format(Locale.US,"%04X:%04X",d.getVendorId(),d.getProductId());
                boolean camera=d.getVendorId()==0x145f && d.getProductId()==0x02ec;
                boolean permission=usb.hasPermission(d);String name=d.getProductName();
                text.append(camera?"【已匹配外接摄像头】\n":"【USB设备】\n").append(id).append(" ").append(name==null?"":name).append("\n访问权限：").append(permission?"已允许":"未允许").append("\n");
                JSONObject entry=new JSONObject();entry.put("vid_pid",id);entry.put("matches_pc_camera",camera);entry.put("permission",permission);JSONArray classes=new JSONArray();
                for(int i=0;i<d.getInterfaceCount();i++){int c=d.getInterface(i).getInterfaceClass();classes.put(c);text.append("接口").append(i).append("：").append(c==14?"视频":c==1?"音频":c==3?"HID":"类别"+c).append("\n");}
                entry.put("interface_classes",classes);entries.put(entry);text.append("\n");
            }
            data.put("devices",entries);
            if(list.isEmpty())text.append("没有设备时，先核对OTG转接与插头。\n系统声明Host不代表实物OTG已通过。\n");
            report.setText(text.toString());
            String key=entries.toString()+host;
            if(!key.equals(lastLog)){lastLog=key;String json=data.toString();Log.i("ZXR_USB_CHECK",json);try(java.io.FileOutputStream f=openFileOutput("latest-usb-check.json",MODE_PRIVATE)){f.write(json.getBytes(java.nio.charset.StandardCharsets.UTF_8));}}
        }catch(Exception e){report.setText("读取USB状态失败："+e.getClass().getSimpleName());}
    }
    public void onResume(){super.onResume();running=true;handler.post(poll);}
    public void onPause(){running=false;handler.removeCallbacks(poll);super.onPause();}
    public void onDestroy(){unregisterReceiver(receiver);super.onDestroy();}
}
