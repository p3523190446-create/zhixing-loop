package cn.zhixing.dashboard;
import java.util.*;

/** Select from advertised modes only. A display resize cannot reduce USB input. */
final class CameraModes {
  static final int MJPEG=7,UNCOMPRESSED=5;
  static final class Mode {
    final int type,width,height;final List<Integer> fps;
    Mode(int t,int w,int h,List<Integer> f){type=t;width=w;height=h;fps=f;}
  }
  static int fps(Mode mode,int requested){
    int under=0,minimum=Integer.MAX_VALUE;
    if(mode.fps!=null)for(Integer value:mode.fps)if(value!=null&&value>0&&value<=120){if(value<=requested)under=Math.max(under,value);minimum=Math.min(minimum,value);}
    return under>0?under:minimum==Integer.MAX_VALUE?0:minimum;
  }
  static Mode choose(List<Mode> modes,int width,int height,int requested){
    Mode best=null;long score=Long.MAX_VALUE;
    for(Mode mode:modes){
      if((mode.type!=MJPEG&&mode.type!=UNCOMPRESSED)||mode.width<=0||mode.height<=0||(mode.width&1)!=0||(mode.height&1)!=0||mode.width>4096||mode.height>4096||fps(mode,requested)==0)continue;
      long pixels=(long)mode.width*mode.height,wanted=(long)width*height;
      int tier=mode.width==width&&mode.height==height?0:mode.width<=width&&mode.height<=height?1:2;
      long value=tier*1000000000L+(mode.type==MJPEG?0:100000000L)+(tier==1?wanted-pixels:pixels);
      if(value<score){score=value;best=mode;}
    }
    return best;
  }
}
