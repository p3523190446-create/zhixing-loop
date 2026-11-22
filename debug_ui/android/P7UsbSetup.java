package cn.zhixing.dashboard;
import android.hardware.usb.*;
import android.os.SystemClock;
import java.io.IOException;

/** Claim the complete CDC function once, then select its data alternate setting.
 * This sends no line coding, no SET_CONFIGURATION and no application commands. */
public final class P7UsbSetup {
  public interface Trace{void stage(String name,int id,boolean accepted,long duration)throws Exception;}
  public static void prepare(UsbDeviceConnection c,UsbInterface control,UsbInterface data,Trace trace)throws Exception{
    if(control==null||data==null||control.getId()==data.getId()||data.getAlternateSetting()!=0)throw new IOException("P7控制／数据接口布局不符");
    boolean heldControl=false,heldData=false;
    try{
      long began=SystemClock.elapsedRealtime();heldControl=c.claimInterface(control,true);trace.stage("native_control_claim",control.getId(),heldControl,SystemClock.elapsedRealtime()-began);
      if(!heldControl)throw new IOException("P7控制接口占用失败，未发送查询");
      began=SystemClock.elapsedRealtime();heldData=c.claimInterface(data,true);trace.stage("native_data_claim",data.getId(),heldData,SystemClock.elapsedRealtime()-began);
      if(!heldData)throw new IOException("P7数据接口占用失败，未发送查询");
      began=SystemClock.elapsedRealtime();boolean selected=c.setInterface(data);trace.stage("native_data_interface_selected",data.getId(),selected,SystemClock.elapsedRealtime()-began);
      if(!selected)throw new IOException("P7数据接口初始化未接受，未发送查询");
    }catch(Exception e){
      if(heldData)try{c.releaseInterface(data);}catch(Exception ignored){}
      if(heldControl)try{c.releaseInterface(control);}catch(Exception ignored){}
      throw e;
    }
  }
}
