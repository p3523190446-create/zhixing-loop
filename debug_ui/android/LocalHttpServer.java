package cn.zhixing.dashboard;
import java.net.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Bounded HTTP/1.0 server, assets and fixed API router only. */
public final class LocalHttpServer {
  private final GatewayService service;private ServerSocket listener;private volatile boolean alive;
  private final RealtimeChannel realtime;
  private final ExecutorService workers=new ThreadPoolExecutor(8,8,30,TimeUnit.SECONDS,new ArrayBlockingQueue<Runnable>(24));
  public LocalHttpServer(GatewayService value){service=value;realtime=new RealtimeChannel(new RealtimeChannel.Source(){
    public JSONObject status()throws Exception{return service.snapshot();}
    public JSONObject command(String path,JSONObject body)throws Exception{return service.post(path,body);}
    public void audit(String event,String detail){service.audit(event,detail);}
  });}
  public void start()throws Exception{Exception failure=null;for(int offset=0;offset<10;offset++){try{listener=new ServerSocket();listener.setReuseAddress(true);listener.bind(new InetSocketAddress("0.0.0.0",GatewayService.PORT+offset));service.boundPort(GatewayService.PORT+offset);failure=null;break;}catch(Exception error){failure=error;try{listener.close();}catch(Exception ignored){}}}if(failure!=null)throw failure;alive=true;new Thread(()->{while(alive)try{Socket socket=listener.accept();if(!socket.getInetAddress().isLoopbackAddress())service.audit("remote_tcp_connected",socket.getInetAddress().getHostAddress());try{workers.execute(()->serve(socket));}catch(RejectedExecutionException e){socket.close();}}catch(Exception e){if(alive)service.audit("http_accept_error",e.toString());}},"onboard-http").start();}
  private String line(InputStream in)throws Exception{ByteArrayOutputStream b=new ByteArrayOutputStream();int n;while((n=in.read())!=-1){if(n=='\n')break;if(n!='\r')b.write(n);if(b.size()>4096)throw new IOException("请求头过长");}return b.toString("US-ASCII");}
  private void serve(Socket socket){try(Socket s=socket){s.setTcpNoDelay(true);s.setSoTimeout(4000);InputStream in=new BufferedInputStream(s.getInputStream());OutputStream out=s.getOutputStream();String[] start=line(in).split(" ");if(start.length!=3)return;String method=start[0],target=start[1];Map<String,String> headers=new HashMap<>();int headerBytes=0;for(;;){String l=line(in);headerBytes+=l.length();if(headerBytes>16384)throw new IOException("请求头超限");if(l.isEmpty())break;int p=l.indexOf(':');if(p>0)headers.put(l.substring(0,p).toLowerCase(Locale.US),l.substring(p+1).trim());}
    int q=target.indexOf('?');String path=q<0?target:target.substring(0,q),query=q<0?"":target.substring(q+1),base=service.base();
    if(!s.getInetAddress().isLoopbackAddress())service.audit("remote_http_received",s.getInetAddress().getHostAddress()+" "+method+" "+(path.startsWith(base)?path.substring(base.length()):"unknown"));
    try{
      if(!path.startsWith(base+"/")&&!path.equals(base)){send(out,404,"application/json",new JSONObject().put("error","地址不存在").toString().getBytes("UTF-8"),null);return;}
      if(method.equals("GET")&&path.equals(base+"/api/realtime")){realtime.serve(s,in,out,headers);return;}
      if(method.equals("GET")&&(path.equals(base)||path.equals(base+"/")||path.equals(base+"/mobile")||path.equals(base+"/mobile-0272")||path.equals(base+"/mobile-0280")||path.equals(base+"/mobile-0286")||path.equals(base+"/desktop"))){String html=new String(asset("web/index.html"),"UTF-8");html=html.replace("href=\"assets/","href=\""+base+"/assets/").replace("src=\"assets/","src=\""+base+"/assets/").replace("<body>","<body data-base=\""+base+"\">").replace("href=\"desktop\"","href=\""+base+"/desktop\"").replace("href=\"mobile\"","href=\""+base+"/mobile\"").replace("href=\"./\"","href=\""+base+"/\"");send(out,200,"text/html; charset=utf-8",html.getBytes("UTF-8"),null);return;}
      if(method.equals("GET")&&path.startsWith(base+"/assets/")){String relative=path.substring((base+"/").length());if(relative.contains("..")||relative.contains("\\")||!relative.matches("assets/[a-zA-Z0-9_/.-]+"))throw new IllegalArgumentException("文件地址错误");send(out,200,relative.endsWith(".js")?"text/javascript; charset=utf-8":"text/css; charset=utf-8",asset("web/"+relative),null);return;}
      if(!path.startsWith(base+"/api/"))throw new IllegalArgumentException("没有这个接口");String api=path.substring((base+"/api/").length());
      if(method.equals("POST")){if(!HttpPostPolicy.allowed(api,headers.get("host"),headers.get("origin"),headers.get("content-type"))){send(out,403,"application/json","{\"error\":\"请从本手机调试页面操作\"}".getBytes("UTF-8"),null);return;}int size=Integer.parseInt(headers.getOrDefault("content-length","0"));if(size<2||size>(api.equals("vlm/analyze")?3100000:512))throw new IllegalArgumentException("请求内容超限");byte[] body=new byte[size];int pos=0;while(pos<size){int n=in.read(body,pos,size-pos);if(n<0)throw new IOException("请求未完整接收");pos+=n;}JSONObject result=service.post(api,new JSONObject(new String(body,"UTF-8")));send(out,200,"application/json; charset=utf-8",result.toString().getBytes("UTF-8"),null);}
      else if(method.equals("GET")){if(api.matches("(photo|record)/[0-9]{8}-[0-9]{6}-[0-9a-f]{6}/(image|video|download)")){
        File media=service.mediaFile(api);sendFile(out,media,api.startsWith("photo/")?"image/jpeg":"video/mp4",headers.get("range"),api.endsWith("/download"));
      }else if(api.equals("camera/frame")){ExternalCamera.Capture frame=service.cameraCapture(query);if(frame==null)send(out,204,"image/jpeg",new byte[0],null);else send(out,200,"image/jpeg",frame.bytes,Long.toString(frame.sequence));}
      else if(api.endsWith("/frame")){byte[] bytes=service.frame(api,query);send(out,200,"image/jpeg",bytes,null);}else{Object result=service.read(api);if(api.equals("ui/info")&&result instanceof JSONObject)((JSONObject)result).put("realtime",new JSONObject().put("websocket",true).put("status_push_hz",10).put("sensor_sampling_hz",1).put("control_requires_mcu_permission",true));send(out,200,"application/json; charset=utf-8",result.toString().getBytes("UTF-8"),null);}}
      else throw new IllegalArgumentException("请求方法错误");
    }catch(Exception error){service.audit("http_error",error.toString());send(out,error instanceof IllegalArgumentException?400:503,"application/json; charset=utf-8",new JSONObject().put("error",error.getMessage()==null?error.toString():error.getMessage()).toString().getBytes("UTF-8"),null);}
  }catch(Exception error){service.audit("http_connection_error",error.toString());}}
  private byte[] asset(String name)throws Exception{try(InputStream in=service.getAssets().open(name);ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[8192];int n;while((n=in.read(b))>0)out.write(b,0,n);return out.toByteArray();}}
  private void send(OutputStream out,int code,String kind,byte[] body,String seq)throws Exception{String header="HTTP/1.0 "+code+" OK\r\nContent-Type: "+kind+"\r\nContent-Length: "+body.length+"\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n"+(seq==null?"":"X-Frame-Seq: "+seq+"\r\n")+"\r\n";out.write(header.getBytes("US-ASCII"));out.write(body);out.flush();}
  private void sendFile(OutputStream out,File file,String kind,String rangeHeader,boolean attachment)throws Exception{
    HttpRange range;long size=file.length();
    try{range=HttpRange.parse(rangeHeader,size);}catch(IllegalArgumentException error){
      out.write(("HTTP/1.1 416 Range Not Satisfiable\r\nContent-Range: bytes */"+size+"\r\nContent-Length: 0\r\nConnection: close\r\n\r\n").getBytes("US-ASCII"));out.flush();return;
    }
    String name=file.getParentFile().getName()+".mp4";
    if(kind.equals("image/jpeg"))name=file.getName();
    String header="HTTP/1.1 "+(range.partial?"206 Partial Content":"200 OK")+"\r\nContent-Type: "+kind+
      "\r\nContent-Length: "+range.length()+"\r\nAccept-Ranges: bytes\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n"+
      (range.partial?"Content-Range: bytes "+range.first+"-"+range.last+"/"+size+"\r\n":"")+
      (attachment?"Content-Disposition: attachment; filename=\""+name+"\"\r\n":"")+"\r\n";
    out.write(header.getBytes("US-ASCII"));
    try(RandomAccessFile input=new RandomAccessFile(file,"r")){input.seek(range.first);byte[] block=new byte[65536];long remaining=range.length();
      while(remaining>0){int read=input.read(block,0,(int)Math.min(block.length,remaining));if(read<0)throw new EOFException("媒体文件被截断");out.write(block,0,read);remaining-=read;}
    }out.flush();
  }
  public void close(){alive=false;realtime.close();try{listener.close();}catch(Exception ignored){}workers.shutdownNow();}
}
