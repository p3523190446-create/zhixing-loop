package cn.zhixing.dashboard;

import java.util.Arrays;

/** Bounded NV21 color components and image-coordinate tracking. No device I/O. */
final class PhoneColorTracker {
  static final String[] MODES={"red","green","blue"};
  static final long REACQUIRE_MS=1000;
  static final class Candidate {
    final String color;final int[] bbox;final int pixels;final double areaFraction;
    Candidate(String color,int[] box,int pixels,int total){this.color=color;this.bbox=box;this.pixels=pixels;areaFraction=(double)pixels/total;}
  }
  static final class Result {
    final long configuration,receivedAt,processingNs;final int width,height;final String mode,state;
    final boolean enabled;final long trackId;final int consistentFrames;final Candidate[] colors;final int[] bbox;
    final Double errorX,errorY,requestX,requestY;
    Result(long config,long at,long ns,int w,int h,String mode,boolean enabled,String state,long id,int count,Candidate[] colors,int[] box,Double x,Double y,Double rx,Double ry){
      configuration=config;receivedAt=at;processingNs=ns;width=w;height=h;this.mode=mode;this.enabled=enabled;this.state=state;trackId=id;consistentFrames=count;this.colors=colors;bbox=box==null?null:box.clone();errorX=x;errorY=y;requestX=rx;requestY=ry;
    }
  }
  private String mode="red";private boolean enabled=true;private long configuration,trackId;
  private int count,missed;private int[] previous;
  private long lastReceivedAt=-1,lastSeenAt=-1;
  private byte[] mask,visited;private int[] queue;
  synchronized long configure(String selected,boolean active){
    if(!Arrays.asList(MODES).contains(selected))throw new IllegalArgumentException("请选择红、绿或蓝色目标");
    mode=selected;enabled=active;configuration++;reset();return configuration;
  }
  synchronized void reset(){previous=null;count=missed=0;lastReceivedAt=lastSeenAt=-1;}
  synchronized String mode(){return mode;}
  synchronized boolean enabled(){return enabled;}
  synchronized long configuration(){return configuration;}
  private static int clamp(int x){return Math.max(0,Math.min(255,x));}
  private static double overlap(int[] a,int[] b){
    int x=Math.max(a[0],b[0]),y=Math.max(a[1],b[1]),r=Math.min(a[0]+a[2],b[0]+b[2]),bottom=Math.min(a[1]+a[3],b[1]+b[3]);
    double area=(double)Math.max(0,r-x)*Math.max(0,bottom-y);
    return area/Math.max(1.,(double)a[2]*a[3]+(double)b[2]*b[3]-area);
  }
  private static double matchScore(int[] a,int[] b,int w,int h){
    double distance=Math.hypot((a[0]+a[2]/2.-b[0]-b[2]/2.)/w,(a[1]+a[3]/2.-b[1]-b[3]/2.)/h);
    double iou=overlap(a,b),ratio=(double)b[2]*b[3]/Math.max(1.,(double)a[2]*a[3]);
    return ratio>=.2&&ratio<=5&&(iou>.05||distance<.2)?distance+.1*(1-iou)+.03*Math.abs(Math.log(ratio)):Double.POSITIVE_INFINITY;
  }
  private Result result(long at,long started,int w,int h,String state,Candidate[] colors,int[] box,Double x,Double y){
    boolean pointing="TRACKING".equals(state);
    Double rx=pointing?(Math.abs(x)<.08?0.:Math.max(-.5,Math.min(.5,x*.5))):null;
    Double ry=pointing?(Math.abs(y)<.08?0.:Math.max(-.5,Math.min(.5,y*.5))):null;
    return new Result(configuration,at,System.nanoTime()-started,w,h,mode,enabled,state,trackId,count,colors,box,x,y,rx,ry);
  }
  synchronized Result process(byte[] raw,int width,int height,long receivedAt,long now){
    long started=System.nanoTime();Candidate[] candidates=new Candidate[3];
    if(width<=0||height<=0||width>4096||height>4096||(width&1)!=0||(height&1)!=0||(long)width*height>4096L*2160||raw==null||raw.length<(long)width*height*3/2)
      throw new IllegalArgumentException("NV21画面尺寸或数据长度错误");
    if(!enabled)return result(receivedAt,started,width,height,"PAUSED",candidates,null,null,null);
    if(now<receivedAt||now-receivedAt>=250){reset();return result(receivedAt,started,width,height,"STALE",candidates,null,null,null);}
    if(lastReceivedAt>=0&&(receivedAt<lastReceivedAt||receivedAt-lastReceivedAt>=250))reset();
    lastReceivedAt=receivedAt;
    if(previous!=null&&receivedAt-lastSeenAt>=REACQUIRE_MS){previous=null;count=0;}
    Candidate associated=null;double bestMatch=Double.POSITIVE_INFINITY;
    int step=Math.max(1,Math.max((width+159)/160,(height+119)/120)),gw=(width+step-1)/step,gh=(height+step-1)/step,total=gw*gh;
    if(mask==null||mask.length!=total){mask=new byte[total];visited=new byte[total];queue=new int[total];}
    Arrays.fill(mask,(byte)0);int plane=width*height;
    for(int gy=0;gy<gh;gy++)for(int gx=0;gx<gw;gx++){
      int x=Math.min(width-1,gx*step),y=Math.min(height-1,gy*step),uv=plane+(y/2)*width+(x&~1);
      int c=Math.max(0,(raw[y*width+x]&255)-16),v=(raw[uv]&255)-128,u=(raw[uv+1]&255)-128;
      int r=clamp((298*c+409*v+128)>>8),g=clamp((298*c-100*u-208*v+128)>>8),b=clamp((298*c+516*u+128)>>8);
      int high=Math.max(r,Math.max(g,b)),low=Math.min(r,Math.min(g,b)),delta=high-low;
      if(delta==0||high==0)continue;
      int saturation=delta*255/high,hue=high==r?30*(g-b)/delta:high==g?60+30*(b-r)/delta:120+30*(r-g)/delta;
      if(hue<0)hue+=180;
      mask[gy*gw+gx]=(byte)(((hue<=10||hue>=170)&&saturation>=110&&high>=80)?1:
                           (hue>=40&&hue<=85&&saturation>=90&&high>=70)?2:
                           (hue>=95&&hue<=130&&saturation>=100&&high>=60)?4:0);
    }
    for(int color=0;color<3;color++){
      Arrays.fill(visited,(byte)0);int flag=1<<color,best=0,bx=0,by=0,br=0,bb=0;
      for(int seed=0;seed<total;seed++){
        if(visited[seed]!=0||(mask[seed]&flag)==0)continue;
        int head=0,tail=0,area=0,left=gw,top=gh,right=0,bottom=0;
        visited[seed]=1;queue[tail++]=seed;
        while(head<tail){
          int p=queue[head++],x=p%gw,y=p/gw;area++;left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);
          if(x>0&&visited[p-1]==0&&(mask[p-1]&flag)!=0){visited[p-1]=1;queue[tail++]=p-1;}
          if(x+1<gw&&visited[p+1]==0&&(mask[p+1]&flag)!=0){visited[p+1]=1;queue[tail++]=p+1;}
          if(y>0&&visited[p-gw]==0&&(mask[p-gw]&flag)!=0){visited[p-gw]=1;queue[tail++]=p-gw;}
          if(y+1<gh&&visited[p+gw]==0&&(mask[p+gw]&flag)!=0){visited[p+gw]=1;queue[tail++]=p+gw;}
        }
        if(previous!=null&&MODES[color].equals(mode)&&area>=Math.max(8,(int)Math.ceil(total*.002))){
          int[] box={left*step,top*step,Math.min(width,(right+1)*step)-left*step,Math.min(height,(bottom+1)*step)-top*step};
          double score=matchScore(previous,box,width,height);
          if(score<bestMatch){bestMatch=score;associated=new Candidate(MODES[color],box,area,total);}
        }
        if(area>best){best=area;bx=left;by=top;br=right;bb=bottom;}
      }
      if(best>=Math.max(8,(int)Math.ceil(total*.002))){
        int left=bx*step,top=by*step,right=Math.min(width,(br+1)*step),bottom=Math.min(height,(bb+1)*step);
        candidates[color]=new Candidate(MODES[color],new int[]{left,top,right-left,bottom-top},best,total);
      }
    }
    Candidate target=candidates[Arrays.asList(MODES).indexOf(mode)];
    if(previous!=null)target=associated;
    if(target==null){missed++;count=0;return result(receivedAt,started,width,height,previous==null?"SEARCHING":"LOST",candidates,null,null,null);}
    int[] box=target.bbox;
    boolean same=previous!=null;
    if(!same){trackId++;count=0;}previous=box.clone();lastSeenAt=receivedAt;missed=0;count++;
    double x=Math.max(-1.,Math.min(1.,(box[0]+box[2]/2.)/(width/2.)-1.));
    double y=Math.max(-1.,Math.min(1.,(box[1]+box[3]/2.)/(height/2.)-1.));
    return result(receivedAt,started,width,height,count>=3?"TRACKING":"LOCKING",candidates,box,x,y);
  }
}
