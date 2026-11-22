package cn.zhixing.dashboard;
import android.hardware.usb.*;
import org.json.*;
import java.util.*;

/** USB classification only. No permission requests, device opens or board commands. */
final class UsbCameraInfo {
  static boolean original(UsbDevice d){return d!=null&&d.getVendorId()==0x145f&&d.getProductId()==0x02ec;}
  static boolean borrowed(UsbDevice d){return d!=null&&d.getVendorId()==0x04b4&&d.getProductId()==0x00c3;}
  static boolean camera(UsbDevice d){
    if(d==null)return false;
    if(d.getVendorId()==0x1a86&&d.getProductId()==0xfe0c)return false;
    if(original(d)||borrowed(d)||d.getDeviceClass()==14)return true;
    for(int n=0;n<d.getInterfaceCount();n++)if(d.getInterface(n).getInterfaceClass()==14)return true;
    return false;
  }
  static String label(UsbDevice d){return original(d)?"原车相机":borrowed(d)?"借用USB031相机":camera(d)?"UVC相机":"其他设备";}
  static String identity(UsbDevice d){return String.format(Locale.US,"%04X:%04X",d.getVendorId(),d.getProductId());}
  static JSONObject describe(UsbDevice d,UsbManager manager)throws JSONException{
    JSONArray interfaces=new JSONArray();
    for(int n=0;n<d.getInterfaceCount();n++){UsbInterface i=d.getInterface(n);interfaces.put(new JSONObject().put("id",i.getId()).put("alternate",i.getAlternateSetting()).put("class",i.getInterfaceClass()).put("subclass",i.getInterfaceSubclass()).put("endpoints",i.getEndpointCount()));}
    return new JSONObject().put("vid_pid",identity(d)).put("label",label(d)).put("camera_candidate",camera(d)).put("permission",manager.hasPermission(d)).put("interfaces",interfaces);
  }
}
