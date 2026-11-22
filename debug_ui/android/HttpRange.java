package cn.zhixing.dashboard;

/** Strict single byte-range support for Safari downloads/seek, without loading whole videos. */
public final class HttpRange {
  public final long first,last;public final boolean partial;
  private HttpRange(long first,long last,boolean partial){this.first=first;this.last=last;this.partial=partial;}
  public long length(){return last-first+1;}
  public static HttpRange parse(String header,long size){
    if(size<=0)throw new IllegalArgumentException("文件为空");
    if(header==null)return new HttpRange(0,size-1,false);
    if(!header.matches("bytes=([0-9]+-[0-9]*|-[0-9]+)"))throw new IllegalArgumentException("仅支持单段字节范围");
    try{
      String spec=header.substring(6);int dash=spec.indexOf('-');long first,last;
      if(dash==0){long suffix=Long.parseLong(spec.substring(1));if(suffix<=0)throw new IllegalArgumentException("空范围");first=Math.max(0,size-suffix);last=size-1;}
      else{first=Long.parseLong(spec.substring(0,dash));last=dash==spec.length()-1?size-1:Long.parseLong(spec.substring(dash+1));if(first>=size||last<first)throw new IllegalArgumentException("范围越界");last=Math.min(last,size-1);}
      return new HttpRange(first,last,true);
    }catch(NumberFormatException error){throw new IllegalArgumentException("范围数字越界",error);}
  }
}
