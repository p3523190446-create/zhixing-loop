package cn.zhixing.dashboard;

/** Phase-based sampling tolerates USB callback jitter without building a queue. */
final class FrameCadence {
  private final long interval,slack;
  private long next=Long.MIN_VALUE;
  FrameCadence(int fps){interval=1000000000L/fps;slack=Math.min(2000000L,interval/4);}
  boolean take(long now){
    if(next==Long.MIN_VALUE){next=now+interval;return true;}
    if(now+slack<next)return false;
    next=Math.max(next+interval,now);
    return true;
  }
}
