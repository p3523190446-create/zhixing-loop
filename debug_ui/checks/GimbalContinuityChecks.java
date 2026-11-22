package cn.zhixing.dashboard;
import java.util.Arrays;

/** Deterministic camera/servo model and NV21 inputs; no physical device I/O. */
public final class GimbalContinuityChecks {
 static int checks;
 static void ok(boolean b,String why){checks++;if(!b)throw new AssertionError(why);}
 static GimbalFollower.Frame f(long n,long t,String state,Double x,Double y){return new GimbalFollower.Frame(n,t,1,8,state,"red",x,y);}
 static GimbalFollower start(double x){GimbalFollower g=new GimbalFollower();g.start(f(1,1000,"TRACKING",x,0.),1000,true,1,1,true,1500,1500,500,2500,500,2500);return g;}
 static byte[] image(int... boxes){int w=160,h=120;byte[] a=new byte[w*h*3/2];Arrays.fill(a,0,w*h,(byte)16);Arrays.fill(a,w*h,a.length,(byte)128);for(int i=0;i<boxes.length;i+=4)for(int y=boxes[i+1];y<boxes[i+1]+boxes[i+3];y++)for(int x=boxes[i];x<boxes[i]+boxes[i+2];x++){a[y*w+x]=(byte)82;int uv=w*h+(y/2)*w+(x&~1);a[uv]=(byte)240;a[uv+1]=(byte)90;}return a;}
 public static void main(String[] args){
  ok(PhoneColorTracker.REACQUIRE_MS==GimbalFollower.REACQUIRE_MS,"identity and control hold windows agree");
  GimbalFollower g=start(.06);g.update(f(2,1100,"TRACKING",.06,0.),1100,true);ok(g.yaw()>1500,"correct an offset inside the old 8 percent dead zone");
  long seq=2;for(long t=1140;t<1500;t+=40)g.update(f(++seq,t,"TRACKING",0.,0.),t,true);ok(g.centered(),"small centered errors settle");int pose=g.yaw();
  g.update(f(++seq,1500,"TRACKING",.022,0.),1500,true);ok(g.yaw()==pose,"hysteresis holds small center jitter");
  g=start(.5);g.update(f(2,1100,"TRACKING",.5,0.),1100,true);pose=g.yaw();
  ok(g.update(f(3,1140,"LOST",null,null),1140,true)&&g.holding(),"one missed detection holds active session");g.holdAt(pose-2,1500);pose=g.yaw();
  ok(g.update(f(4,1180,"LOCKING",.5,0.),1180,true)&&g.yaw()==pose,"relocking frame does not integrate stale error");
  ok(g.update(f(5,1220,"TRACKING",.5,0.),1220,true)&&!g.holding()&&g.yaw()==pose,"first recovered frame resumes without catch-up jump");
  ok(g.update(f(6,1260,"TRACKING",.5,0.),1260,true)&&g.yaw()>pose,"subsequent fresh observation follows again");
  g=start(.5);for(int i=1;i<=24;i++){long t=1000+i*40;if(i%5==0)g.heartbeat(t);ok(g.update(f(i+1,t,"LOST",null,null),t,true),"short loss remains bounded hold");}
  ok(g.update(f(26,2000,"LOST",null,null),2000,true)&&g.holding(),"fresh camera and live lease keep waiting beyond one second");
  g.stop("explicit stop");
  ok(!g.update(f(27,2040,"TRACKING",.5,0.),2040,true),"ended session does not automatically restart");
  g=start(.5);ok(!g.update(f(2,1000,"LOST",null,null),1250,true),"camera staleness still stops immediately");
  g=start(.5);ok(g.update(new GimbalFollower.Frame(2,1040,1,9,"TRACKING","red",.5,0.),1040,true)&&g.holding()&&g.yaw()==1500,"stable selected color can renew identity without a jump");
  // A larger distractor appearing elsewhere must not steal the original red block.
  PhoneColorTracker tracker=new PhoneColorTracker();PhoneColorTracker.Result r=null;
  for(int n=0;n<3;n++)r=tracker.process(image(20,40,20,20),160,120,1000+n*40,1000+n*40);long id=r.trackId;
  r=tracker.process(image(22,40,20,20,110,40,32,32),160,120,1120,1120);ok(r.trackId==id&&r.bbox[0]<50,"near original selected over a larger distant same-color distractor");
  r=tracker.process(image(110,40,32,32),160,120,1160,1160);ok(r.state.equals("LOST")&&r.bbox==null,"distant same-color replacement is not the original");
  for(int n=0;n<10;n++)r=tracker.process(image(),160,120,1200+n*40,1200+n*40);
  for(int n=0;n<3;n++)r=tracker.process(image(24,40,20,20),160,120,1600+n*40,1600+n*40);
  ok(r.state.equals("TRACKING")&&r.trackId==id,"short occlusion reacquires original identity after three frames");
  for(int n=0;n<28;n++)r=tracker.process(image(),160,120,1720+n*40,1720+n*40);
  ok(r.state.equals("SEARCHING"),"long visual loss releases identity");
  for(int n=0;n<3;n++)r=tracker.process(image(110,40,32,32),160,120,2840+n*40,2840+n*40);
  ok(r.trackId!=id,"a newly acquired object has a new identity");
  // Assumed linear servo response, 80 ms image delay, 25 FPS, both mount signs.
  double worst=0;
  for(int sign:new int[]{-1,1}){
   g=new GimbalFollower();g.start(f(1,1000,"TRACKING",.6,-.4),1000,true,sign,sign,true,1500,1500,500,2500,500,2500);
   double[] ys=new double[152],ps=new double[152];ys[0]=ps[0]=1500;long n=1;
   for(int i=1;i<=150;i++){
    long t=1000+i*40;if(i%8==0)g.heartbeat(t);int delayed=Math.max(0,i-2);
    double x=.6-(ys[delayed]-1500)*.003*sign,y=-.4-(ps[delayed]-1500)*.003*sign;
    boolean missed=i==15||i==16;ok(g.update(f(++n,t,missed?"LOST":"TRACKING",missed?null:x,missed?null:y),t,true),"modeled closed loop remains enabled");
    if(g.holding())g.holdAt((int)ys[i-1],(int)ps[i-1]);ys[i]=g.yaw();ps[i]=g.pitch();
   }
   double error=Math.max(Math.abs(.6-(g.yaw()-1500)*.003*sign),Math.abs(-.4-(g.pitch()-1500)*.003*sign));worst=Math.max(worst,error);ok(error<.035,"delayed modeled target converges near center");
  }
  System.out.println("{\"continuity_checks\":"+checks+",\"result\":\"PASS\",\"simulated_final_error\":"+worst+",\"physical_motion\":false}");
 }
}
