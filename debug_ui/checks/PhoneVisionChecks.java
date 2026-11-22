package cn.zhixing.dashboard;

import java.util.Arrays;
import org.json.*;

/** Controlled NV21/time inputs; real Android execution is recorded separately. */
public final class PhoneVisionChecks {
  private static int checks;
  private static void check(boolean value){checks++;if(!value)throw new AssertionError("check "+checks);}
  private static byte[] blank(){byte[] raw=new byte[640*480*3/2];Arrays.fill(raw,0,640*480,(byte)235);Arrays.fill(raw,640*480,raw.length,(byte)128);return raw;}
  private static void rectangle(byte[] raw,int left,int top,int width,int height,int y,int v,int u){
    for(int row=top;row<top+height;row++)for(int col=left;col<left+width;col++)raw[row*640+col]=(byte)y;
    for(int row=top;row<top+height;row+=2)for(int col=left;col<left+width;col+=2){int p=640*480+(row/2)*640+col;raw[p]=(byte)v;raw[p+1]=(byte)u;}
  }
  public static void main(String[] args)throws Exception {
    byte[] raw=blank();rectangle(raw,40,120,120,120,82,240,90);rectangle(raw,260,120,120,120,145,34,54);rectangle(raw,480,120,120,120,41,110,240);
    PhoneColorTracker tracker=new PhoneColorTracker();
    PhoneColorTracker.Result a=tracker.process(raw,640,480,1000,1010);check(a.state.equals("LOCKING"));check(a.colors[0]!=null&&a.colors[1]!=null&&a.colors[2]!=null);
    tracker.process(raw,640,480,1033,1040);PhoneColorTracker.Result locked=tracker.process(raw,640,480,1066,1070);
    check(locked.state.equals("TRACKING"));check(locked.errorX<-.6);check(locked.requestX<0);check(Math.abs(locked.bbox[0]-40)<=4);
    PhoneColorTracker.Result missing=tracker.process(blank(),640,480,1100,1110);check(missing.state.equals("LOST"));check(missing.requestX==null&&missing.bbox==null);
    tracker.process(blank(),640,480,1133,1140);check(tracker.process(blank(),640,480,1166,1170).state.equals("LOST"));
    for(String mode:PhoneColorTracker.MODES){tracker.configure(mode,true);for(int n=0;n<3;n++)locked=tracker.process(raw,640,480,2000+n*40,2005+n*40);check(locked.state.equals("TRACKING"));check(locked.mode.equals(mode));}
    PhoneColorTracker.Result gap=tracker.process(raw,640,480,4000,4001);check(gap.state.equals("LOCKING"));check(gap.requestX==null);
    check(tracker.process(raw,640,480,4000,4250).state.equals("STALE"));check(tracker.process(raw,640,480,4000,3999).state.equals("STALE"));
    tracker.configure("red",false);check(tracker.process(raw,640,480,5000,5001).state.equals("PAUSED"));
    boolean rejected=false;try{tracker.configure("face",true);}catch(IllegalArgumentException e){rejected=true;}check(rejected);
    rejected=false;try{tracker.process(new byte[2],640,480,5000,5001);}catch(IllegalArgumentException e){rejected=true;}check(rejected);
    byte[] tiny=blank();rectangle(tiny,40,120,4,4,82,240,90);tracker.configure("red",true);check(tracker.process(tiny,640,480,6000,6001).bbox==null);
    byte[] center=blank();rectangle(center,280,200,80,80,82,240,90);for(int n=0;n<3;n++)locked=tracker.process(center,640,480,7000+n*40,7001+n*40);check(locked.requestX==0.&&locked.requestY==0.);

    FrameCadence clock=new FrameCadence(15);int phase=0,old=0;long oldAt=Long.MIN_VALUE;
    for(int n=0;n<240;n++){long t=n*1000000000L/24;if(clock.take(t))phase++;long ms=t/1000000;if(oldAt==Long.MIN_VALUE||ms-oldAt>=1000/15){old++;oldAt=ms;}}
    check(phase>=149&&phase<=151);check(old==120);
    clock=new FrameCadence(30);int full=0;for(int n=0;n<240;n++)if(clock.take(n*1000000000L/24))full++;check(full==240);
    clock=new FrameCadence(15);check(clock.take(0));check(clock.take(1000000000L));check(!clock.take(1000000000L));
    rejected=false;try{new FrameCadence(0);}catch(IllegalArgumentException e){rejected=true;}check(rejected);

    PhoneVision vision=new PhoneVision();PhoneColorTracker.Result frame=null;
    for(int n=0;n<3;n++){frame=vision.process(raw,640,480,8000+n*40,8001+n*40);vision.publish(frame,n+1);}
    JSONObject fresh=vision.status(8090);check(fresh.getBoolean("valid"));check(fresh.getString("state").equals("TRACKING"));check(!fresh.getBoolean("actuation_enabled"));check(fresh.getLong("frame_seq")==3);
    JSONObject stale=vision.status(8330);check(!stale.getBoolean("valid"));check(stale.isNull("bbox")&&stale.isNull("pointing_request"));
    vision.configure(new JSONObject().put("mode","blue"),8400);vision.publish(frame,4);check(!vision.status(8400).getBoolean("valid"));
    rejected=false;try{vision.configure(new JSONObject().put("actuate",true),8500);}catch(IllegalArgumentException e){rejected=true;}check(rejected);
    rejected=false;try{vision.configure(new JSONObject().put("enabled","yes"),8500);}catch(IllegalArgumentException e){rejected=true;}check(rejected);
    for(int n=0;n<25;n++)tracker.process(raw,640,480,9000+n*40,9001+n*40);
    long[] times=new long[120];for(int n=0;n<times.length;n++){long start=System.nanoTime();tracker.process(raw,640,480,10000+n*40,10001+n*40);times[n]=System.nanoTime()-start;}
    Arrays.sort(times);JSONObject report=new JSONObject().put("checks",checks).put("controlled_nv21",true).put("phase_selected_frames",phase).put("legacy_selected_frames",old)
      .put("median_color_ms",times[times.length/2]/1000000.).put("p95_color_ms",times[(int)(times.length*.95)]/1000000.)
      .put("live_camera_acceptance",false).put("actuator_commands_sent",false);
    System.out.println(report.toString());
  }
}
