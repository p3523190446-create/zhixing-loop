package cn.zhixing.dashboard;
import android.content.*;import android.hardware.usb.*;import android.os.*;import org.json.*;import java.util.*;import java.util.function.BiConsumer;
/** Passive observer only. Never requests permission, opens USB or retries control. */
public final class UsbInventoryMonitor {
 private final Context context;private final UsbManager manager;private final BiConsumer<String,String> log;private final Handler timer=new Handler();
 private String previous="";private long last;private boolean closed;
 public UsbInventoryMonitor(Context c,BiConsumer<String,String> write){context=c;manager=(UsbManager)c.getSystemService(Context.USB_SERVICE);log=write;IntentFilter f=new IntentFilter(UsbManager.ACTION_USB_DEVICE_ATTACHED);f.addAction(UsbManager.ACTION_USB_DEVICE_DETACHED);c.registerReceiver(events,f);timer.post(tick);}
 private final BroadcastReceiver events=new BroadcastReceiver(){public void onReceive(Context c,Intent i){try{UsbDevice d=i.getParcelableExtra(UsbManager.EXTRA_DEVICE);JSONObject e=new JSONObject().put("action",i.getAction());if(d!=null)e.put("device",describe(d));log.accept("usb_attach_detach",e.toString());sample(true);}catch(Exception e){log.accept("usb_inventory_error",e.toString());}}};
 private JSONObject describe(UsbDevice d)throws Exception{return new JSONObject().put("device_name",d.getDeviceName()).put("vid",d.getVendorId()).put("pid",d.getProductId()).put("interfaces",d.getInterfaceCount()).put("permission",manager.hasPermission(d));}
 private void sample(boolean force){try{Map<String,UsbDevice> all=manager.getDeviceList();JSONArray a=new JSONArray();for(String key:new TreeSet<String>(all.keySet()))a.put(describe(all.get(key)));String signature=a.toString();long now=SystemClock.elapsedRealtime();if(force||!signature.equals(previous)||now-last>=60000){log.accept("usb_inventory_snapshot",new JSONObject().put("version","0.10").put("devices",a).put("target","1A86:FE0C").put("observer_only",true).toString());previous=signature;last=now;}}catch(Exception e){log.accept("usb_inventory_error",e.toString());}}
 private final Runnable tick=new Runnable(){public void run(){if(closed)return;sample(false);timer.postDelayed(this,1000);}};
 public void close(){closed=true;timer.removeCallbacksAndMessages(null);context.unregisterReceiver(events);}
}
