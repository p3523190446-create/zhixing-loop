package cn.zhixing.dashboard;

/** Pure bounded image-error controller; device I/O stays in ControlBroker. */
final class GimbalFollower {
  static final long FRAME_TTL_MS=250,LEASE_MS=1500,REACQUIRE_MS=1000;
  static final double DEAD_ZONE=.015,RESUME_ZONE=.025,MAX_RATE_US=600.,GAIN_US=900.;
  static final class Frame {
    final long sequence,receivedAt,configuration,trackId;final String state,mode;
    final Double x,y;
    Frame(long sequence,long receivedAt,long configuration,long trackId,String state,String mode,Double x,Double y){
      this.sequence=sequence;this.receivedAt=receivedAt;this.configuration=configuration;this.trackId=trackId;
      this.state=state;this.mode=mode;this.x=x;this.y=y;
    }
  }
  interface Source {Frame latest();boolean stationary();}
  private boolean active;private long touched,lastAt,sequence,receivedAt,configuration,trackId;
  private int yawSign,pitchSign,yawMin,yawMax,pitchMin,pitchMax;private boolean both;
  private double yaw,pitch,filteredX,filteredY;
  private boolean holding,yawCentered,pitchCentered;
  private String reason="尚未启动",mode="";
  boolean active(){return active;}String reason(){return reason;}String mode(){return mode;}
  boolean holding(){return holding;}boolean centered(){return !holding&&yawCentered&&(!both||pitchCentered);}
  double errorX(){return filteredX;}double errorY(){return filteredY;}
  void holdAt(int sentYaw,int sentPitch){if(holding){yaw=sentYaw;pitch=sentPitch;}}
  int yaw(){return (int)Math.round(yaw);}int pitch(){return (int)Math.round(pitch);}
  int yawMin(){return yawMin;}int yawMax(){return yawMax;}int pitchMin(){return pitchMin;}int pitchMax(){return pitchMax;}
  private static boolean finite(Double v){return v!=null&&!Double.isNaN(v)&&!Double.isInfinite(v)&&v>=-1&&v<=1;}
  static boolean fresh(Frame f,long now){return f!=null&&now>=f.receivedAt&&now-f.receivedAt<FRAME_TTL_MS
    &&"TRACKING".equals(f.state)&&finite(f.x)&&finite(f.y);}
  void start(Frame frame,long now,boolean stationary,int ys,int ps,boolean both,int currentYaw,int currentPitch,int yLo,int yHi,int pLo,int pHi){
    if(!stationary)throw new IllegalStateException("请先停住车轮和循迹任务，再启动云台跟随");
    if(!fresh(frame,now))throw new IllegalStateException("请先让所选色块连续锁定，再开启跟随");
    if((ys!=1&&ys!=-1)||(ps!=1&&ps!=-1))throw new IllegalArgumentException("跟随方向需要正向或反向");
    if(yLo<500||yHi>2500||pLo<500||pHi>2500||currentYaw<yLo||currentYaw>yHi||currentPitch<pLo||currentPitch>pHi)
      throw new IllegalStateException("当前位置不在已设置的云台范围内");
    yawMin=yLo;yawMax=yHi;pitchMin=pLo;pitchMax=pHi;
    yaw=currentYaw;pitch=currentPitch;yawSign=ys;pitchSign=ps;this.both=both;
    sequence=frame.sequence;receivedAt=frame.receivedAt;configuration=frame.configuration;trackId=frame.trackId;mode=frame.mode;
    touched=lastAt=now;holding=false;filteredX=frame.x;filteredY=frame.y;
    yawCentered=Math.abs(filteredX)<=DEAD_ZONE;pitchCentered=Math.abs(filteredY)<=DEAD_ZONE;
    active=true;reason="跟随中";
  }
  void heartbeat(long now){if(!active||now<touched||now-touched>=LEASE_MS){stop("页面心跳过期，已撤销跟随");throw new IllegalStateException(reason);}touched=now;}
  void stop(String why){active=false;reason=why;}
  private static double velocity(double error){
    if(Math.abs(error)<=DEAD_ZONE)return 0;
    // Reduce gain near center to tolerate the camera/USB/servo delay and backlash.
    double gain=300.+(GAIN_US-300.)*Math.min(1.,Math.abs(error)/.3);
    return Math.max(-MAX_RATE_US,Math.min(MAX_RATE_US,error*gain));
  }
  private static double bound(double n,int low,int high){return Math.max(low,Math.min(high,n));}
  /** Fresh missed detections hold position briefly; stale camera/lease still revokes. */
  boolean update(Frame frame,long now,boolean stationary){
    if(!active)return false;
    if(now<touched||now<lastAt||now-touched>=LEASE_MS){stop("页面心跳过期，已撤销跟随");return false;}
    if(!stationary){stop("车辆状态改变，已撤销跟随");return false;}
    if(frame==null||now<frame.receivedAt||now-frame.receivedAt>=FRAME_TTL_MS){stop("相机画面过期，已撤销跟随");return false;}
    if(frame.configuration!=configuration||!mode.equals(frame.mode)){
      stop("跟踪设置改变，请重新启动");return false;
    }
    if(frame.sequence<sequence||frame.receivedAt<receivedAt){stop("相机序号回退，请重新启动");return false;}
    if(frame.sequence==sequence)return true;
    sequence=frame.sequence;receivedAt=frame.receivedAt;
    if(!"TRACKING".equals(frame.state)){
      if(!"LOST".equals(frame.state)&&!"LOCKING".equals(frame.state)&&!"SEARCHING".equals(frame.state)){stop("视觉跟踪已暂停，已撤销跟随");return false;}
      holding=true;lastAt=now;reason="等待所选颜色重新锁定，云台保持位置";return true;
    }
    if(!finite(frame.x)||!finite(frame.y)){stop("目标位置无效，已撤销跟随");return false;}
    if(frame.trackId!=trackId){trackId=frame.trackId;holding=true;lastAt=now;reason="所选颜色已重锁，正在恢复跟随";return true;}
    double dt=Math.max(0,Math.min(200,now-lastAt))/1000.;lastAt=now;
    if(holding){filteredX=frame.x;filteredY=frame.y;holding=false;dt=0;}
    double alpha=dt/(.045+dt);filteredX+=alpha*(frame.x-filteredX);filteredY+=alpha*(frame.y-filteredY);
    yawCentered=Math.abs(filteredX)<=(yawCentered?RESUME_ZONE:DEAD_ZONE);
    pitchCentered=Math.abs(filteredY)<=(pitchCentered?RESUME_ZONE:DEAD_ZONE);
    yaw=bound(yaw+(yawCentered?0:yawSign*velocity(filteredX)*dt),yawMin,yawMax);
    if(both)pitch=bound(pitch+(pitchCentered?0:pitchSign*velocity(filteredY)*dt),pitchMin,pitchMax);
    reason=centered()?"目标已居中":"正在向画面中心对准";
    return true;
  }
}
