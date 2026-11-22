package cn.zhixing.dashboard;
import java.nio.ByteBuffer;

/** BT.601 limited-range 4:2:0; honors both planar and interleaved plane strides. */
public final class Yuv420 {
  private static int clip(int value){return Math.max(0,Math.min(255,value));}
  private static void validate(ByteBuffer buffer,int width,int height,int rowStride,int pixelStride){
    if(rowStride<=0||pixelStride<=0||(long)buffer.position()+(long)(height-1)*rowStride+(long)(width-1)*pixelStride>=buffer.limit())
      throw new IllegalArgumentException("YUV输入平面容量或步长不足");
  }
  public static void convert(int[] rgb,int width,int height,
      ByteBuffer y,int ys,int yp,ByteBuffer u,int us,int up,ByteBuffer v,int vs,int vp){
    if(width<2||height<2||(width&1)!=0||(height&1)!=0||(long)width*height>rgb.length)throw new IllegalArgumentException("YUV画面尺寸错误");
    validate(y,width,height,ys,yp);validate(u,width/2,height/2,us,up);validate(v,width/2,height/2,vs,vp);
    int yBase=y.position(),uBase=u.position(),vBase=v.position();
    for(int row=0;row<height;row++)for(int col=0;col<width;col++){
      int pixel=rgb[row*width+col],r=(pixel>>16)&255,g=(pixel>>8)&255,b=pixel&255;
      y.put(yBase+row*ys+col*yp,(byte)clip(((66*r+129*g+25*b+128)>>8)+16));
      if((row&1)==0&&(col&1)==0){
        int rr=0,gg=0,bb=0;
        for(int dy=0;dy<2;dy++)for(int dx=0;dx<2;dx++){int c=rgb[(row+dy)*width+col+dx];rr+=(c>>16)&255;gg+=(c>>8)&255;bb+=c&255;}
        rr/=4;gg/=4;bb/=4;
        u.put(uBase+row/2*us+col/2*up,(byte)clip(((-38*rr-74*gg+112*bb+128)>>8)+128));
        v.put(vBase+row/2*vs+col/2*vp,(byte)clip(((112*rr-94*gg-18*bb+128)>>8)+128));
      }
    }
  }
}
