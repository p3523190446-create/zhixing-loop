package cn.zhixing.dashboard;

import android.graphics.*;
import android.media.*;
import java.io.*;
import java.nio.ByteBuffer;

/** JPEG reception times become monotonic H.264/MP4 presentation timestamps. */
public final class Mp4Writer implements Closeable {
  private MediaCodec codec;private MediaMuxer muxer;private int track=-1;
  private boolean started,closed;private final int width,height;private long lastPts=-1;
  private int[] pixels;public long encoded,dropped;
  public Mp4Writer(File destination,int width,int height,int fps)throws Exception{
    if(width<2||height<2||(width&1)!=0||(height&1)!=0)throw new IOException("MP4画面尺寸必须为偶数");
    this.width=width;this.height=height;pixels=new int[width*height];
    try{
      codec=MediaCodec.createEncoderByType("video/avc");
      MediaFormat format=MediaFormat.createVideoFormat("video/avc",width,height);
      format.setInteger(MediaFormat.KEY_COLOR_FORMAT,MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible);
      format.setInteger(MediaFormat.KEY_BIT_RATE,Math.max(500000,Math.min(6000000,width*height*6)));
      format.setInteger(MediaFormat.KEY_FRAME_RATE,Math.max(1,Math.min(30,fps)));
      format.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL,1);
      codec.configure(format,null,null,MediaCodec.CONFIGURE_FLAG_ENCODE);codec.start();
      muxer=new MediaMuxer(destination.getAbsolutePath(),MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);
    }catch(Exception error){if(codec!=null){try{codec.release();}catch(Exception ignored){}}throw error;}
  }
  public void frame(byte[] jpeg,long timestampUs)throws Exception{
    if(closed)throw new IOException("录像编码器已关闭");drain(false);
    int slot=codec.dequeueInputBuffer(10000);if(slot<0){dropped++;return;}
    Bitmap bitmap=BitmapFactory.decodeByteArray(jpeg,0,jpeg.length);
    if(bitmap==null)throw new IOException("录像帧JPEG无法解码");
    Image image=null;
    try{
      if(bitmap.getWidth()!=width||bitmap.getHeight()!=height)throw new IOException("录像期间画面尺寸变化");
      bitmap.getPixels(pixels,0,width,0,0,width,height);image=codec.getInputImage(slot);
      if(image==null)throw new IOException("本机编码器不提供YUV输入图像");
      Image.Plane[] planes=image.getPlanes();
      Yuv420.convert(pixels,width,height,
        planes[0].getBuffer(),planes[0].getRowStride(),planes[0].getPixelStride(),
        planes[1].getBuffer(),planes[1].getRowStride(),planes[1].getPixelStride(),
        planes[2].getBuffer(),planes[2].getRowStride(),planes[2].getPixelStride());
      long pts=Math.max(lastPts+1,timestampUs);lastPts=pts;
      int inputSize=width*height*3/2;image.close();image=null;
      codec.queueInputBuffer(slot,0,inputSize,pts,0);encoded++;drain(false);
    }finally{if(image!=null)image.close();bitmap.recycle();}
  }
  private void drain(boolean untilEnd)throws Exception{
    MediaCodec.BufferInfo info=new MediaCodec.BufferInfo();long deadline=android.os.SystemClock.elapsedRealtime()+2500;
    do{
      int slot=codec.dequeueOutputBuffer(info,untilEnd?10000:0);
      if(slot==MediaCodec.INFO_OUTPUT_FORMAT_CHANGED){
        if(started)throw new IOException("录像编码格式重复变更");track=muxer.addTrack(codec.getOutputFormat());muxer.start();started=true;
      }else if(slot>=0){
        ByteBuffer buffer=codec.getOutputBuffer(slot);
        try{
          if((info.flags&MediaCodec.BUFFER_FLAG_CODEC_CONFIG)!=0)info.size=0;
          if(info.size>0){if(!started)throw new IOException("MP4轨道尚未启动");buffer.position(info.offset);buffer.limit(info.offset+info.size);muxer.writeSampleData(track,buffer,info);}
        }finally{codec.releaseOutputBuffer(slot,false);}
        if((info.flags&MediaCodec.BUFFER_FLAG_END_OF_STREAM)!=0)return;
      }else if(slot==MediaCodec.INFO_TRY_AGAIN_LATER&&!untilEnd)return;
    }while(android.os.SystemClock.elapsedRealtime()<deadline);
    if(untilEnd)throw new IOException("MP4结束标记超时");
  }
  public void close()throws IOException{
    if(closed)return;closed=true;Exception failure=null;
    try{
      int slot=codec.dequeueInputBuffer(30000);
      if(slot<0)throw new IOException("MP4无法提交结束标记");
      codec.queueInputBuffer(slot,0,0,Math.max(0,lastPts+1),MediaCodec.BUFFER_FLAG_END_OF_STREAM);drain(true);
    }catch(Exception error){failure=error;}
    finally{
      try{codec.stop();}catch(Exception error){if(failure==null)failure=error;}codec.release();
      try{if(started)muxer.stop();}catch(Exception error){if(failure==null)failure=error;}finally{muxer.release();}
    }
    if(failure!=null)throw new IOException("MP4保存失败",failure);
    if(!started||encoded==0)throw new IOException("没有可保存的录像帧");
  }
}
