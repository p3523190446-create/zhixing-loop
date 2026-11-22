package cn.zhixing.dashboard;

import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Bounded same-origin WebSocket for latest status and fixed gimbal commands.
 * It never owns USB and never grants capabilities. Source remains authoritative.
 * Video is kept off this socket. Slow clients are closed, not queued indefinitely.
 */
public final class RealtimeChannel {
  public interface Source {
    JSONObject status() throws Exception;
    JSONObject command(String path,JSONObject body) throws Exception;
    void audit(String event,String detail);
  }
  private final Source source;
  private final Semaphore slots=new Semaphore(3);
  private final Set<Socket> sockets=Collections.synchronizedSet(new HashSet<Socket>());
  private static final Set<String> COMMANDS=new HashSet<>(Arrays.asList(
    "gimbal/start","gimbal/set","gimbal/center","gimbal/heartbeat","gimbal/stop"));
  private static final int MAX_FRAME=1024;
  private static final long WRITE_LIMIT_NS=TimeUnit.SECONDS.toNanos(2);
  private final ScheduledExecutorService watchdog=Executors.newSingleThreadScheduledExecutor(r->{Thread t=new Thread(r,"realtime-watchdog");t.setDaemon(true);return t;});
  private final ExecutorService commands=new ThreadPoolExecutor(2,2,30,TimeUnit.SECONDS,new ArrayBlockingQueue<Runnable>(8),r->{Thread t=new Thread(r,"realtime-command");t.setDaemon(true);return t;});
  private final ExecutorService stops=new ThreadPoolExecutor(1,1,30,TimeUnit.SECONDS,new ArrayBlockingQueue<Runnable>(3),r->{Thread t=new Thread(r,"realtime-stop");t.setDaemon(true);return t;});
  private volatile boolean closed;
  public RealtimeChannel(Source value){source=value;}
  public static boolean commandAllowed(String path){return COMMANDS.contains(path);}
  private static long mono(){return System.nanoTime()/1000000L;}
  public boolean serve(Socket socket,InputStream input,OutputStream output,Map<String,String> headers)throws Exception{
    String host=headers.get("host"),origin=headers.get("origin"),key=headers.get("sec-websocket-key");
    boolean valid=host!=null&&("http://"+host).equals(origin)
      &&"websocket".equalsIgnoreCase(headers.get("upgrade"))
      &&Arrays.asList(headers.getOrDefault("connection","").toLowerCase(Locale.US).split("\\s*,\\s*")).contains("upgrade")
      &&"13".equals(headers.get("sec-websocket-version"));
    try{valid=valid&&key!=null&&Base64.getDecoder().decode(key).length==16;}catch(IllegalArgumentException e){valid=false;}
    if(!valid){reject(output,403);return false;}
    if(closed||!slots.tryAcquire()){reject(output,503);return false;}
    sockets.add(socket);AtomicBoolean alive=new AtomicBoolean(true);
    AtomicLong writing=new AtomicLong(0),lastRead=new AtomicLong(System.nanoTime());
    Thread publisher=null;ScheduledFuture<?> guard=null;
    try{
      socket.setTcpNoDelay(true);socket.setSoTimeout(6000);
      String accept=Base64.getEncoder().encodeToString(MessageDigest.getInstance("SHA-1").digest((key+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").getBytes(StandardCharsets.US_ASCII)));
      output.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: "+accept+"\r\n\r\n").getBytes(StandardCharsets.US_ASCII));output.flush();
      final Object sendLock=new Object();
      Sender sender=new Sender(output,sendLock,writing);
      guard=watchdog.scheduleAtFixedRate(()->{
        long now=System.nanoTime(),began=writing.get();
        if((began>0&&now-began>WRITE_LIMIT_NS)||now-lastRead.get()>TimeUnit.SECONDS.toNanos(6))closeSocket(socket);
      },250,250,TimeUnit.MILLISECONDS);
      publisher=new Thread(()->{
        long seq=0;
        while(alive.get()&&!closed)try{
          // At most one status write at a time; no historical status queue.
          JSONObject data=source.status();
          sender.json(new JSONObject().put("type","status").put("seq",++seq).put("server_mono_ms",mono()).put("data",data));
          Thread.sleep(100);
        }catch(Exception error){alive.set(false);closeSocket(socket);}
      },"realtime-latest-status");publisher.setDaemon(true);publisher.start();
      source.audit("realtime_connected","latest status + allowlisted commands; no USB ownership");
      while(alive.get()&&!closed){
        Frame frame=readFrame(input);lastRead.set(System.nanoTime());
        if(frame.op==8){sender.frame(8,frame.bytes.length>=2?Arrays.copyOf(frame.bytes,2):new byte[0]);break;}
        if(frame.op==9){sender.frame(10,frame.bytes);continue;}
        if(frame.op==10)continue;
        if(frame.op!=1)throw new IOException("Only bounded text messages are accepted");
        JSONObject request=new JSONObject(new String(frame.bytes,StandardCharsets.UTF_8));
        String type=request.optString("type"),id=request.optString("id");
        if(!id.matches("[A-Za-z0-9_-]{1,48}"))throw new IOException("Invalid message id");
        if(type.equals("ping")){sender.json(new JSONObject().put("type","pong").put("id",id).put("server_mono_ms",mono()));continue;}
        if(!type.equals("command"))throw new IOException("Unknown message type");
        String path=request.optString("path");JSONObject body=request.optJSONObject("body");
        if(!commandAllowed(path)||body==null||body.toString().getBytes(StandardCharsets.UTF_8).length>512){sender.json(new JSONObject().put("type","reply").put("id",id).put("ok",false).put("error","Command not allowed"));continue;}
        Runnable job=()->{
          if(!alive.get()||socket.isClosed())return; // Never replay queued operations after disconnect.
          JSONObject reply=new JSONObject();long began=mono();
          try{reply.put("type","reply").put("id",id);
            // Source/USB owner still checks capabilities, lease and firmware replies.
            reply.put("ok",true).put("data",source.command(path,body));
          }catch(Exception error){try{reply.put("ok",false).put("error",error.getMessage()==null?error.toString():error.getMessage());}catch(JSONException ignored){}}
          try{reply.put("server_processing_ms",mono()-began);if(alive.get())sender.json(reply);}catch(Exception ignored){alive.set(false);closeSocket(socket);}
        };
        try{(path.equals("gimbal/stop")?stops:commands).execute(job);}
        catch(RejectedExecutionException error){sender.json(new JSONObject().put("type","reply").put("id",id).put("ok",false).put("error","Request capacity exceeded"));}
      }
      return true;
    }finally{
      alive.set(false);closeSocket(socket);if(guard!=null)guard.cancel(false);
      if(publisher!=null){publisher.interrupt();publisher.join(500);}
      sockets.remove(socket);slots.release();source.audit("realtime_closed","No command replay or automatic arm");
    }
  }
  private static void reject(OutputStream out,int code)throws IOException{byte[] b="{\"error\":\"Realtime connection rejected\"}".getBytes(StandardCharsets.UTF_8);out.write(("HTTP/1.1 "+code+" Rejected\r\nContent-Type: application/json\r\nContent-Length: "+b.length+"\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.US_ASCII));out.write(b);out.flush();}
  private static class Sender {
    final OutputStream out;final Object lock;final AtomicLong writing;
    Sender(OutputStream value,Object mutex,AtomicLong clock){out=value;lock=mutex;writing=clock;}
    void json(JSONObject object)throws IOException{frame(1,object.toString().getBytes(StandardCharsets.UTF_8));}
    void frame(int opcode,byte[] bytes)throws IOException{
      if(bytes.length>65535)throw new IOException("Status frame too large");
      synchronized(lock){writing.set(System.nanoTime());try{out.write(0x80|opcode);if(bytes.length<126)out.write(bytes.length);else{out.write(126);out.write(bytes.length>>>8);out.write(bytes.length&255);}out.write(bytes);out.flush();}finally{writing.set(0);}}
    }
  }
  private static class Frame{int op;byte[] bytes;Frame(int o,byte[] b){op=o;bytes=b;}}
  private static int byteAt(InputStream in)throws IOException{int value=in.read();if(value<0)throw new EOFException();return value;}
  private static Frame readFrame(InputStream in)throws IOException{
    int first=byteAt(in),second=byteAt(in),op=first&15;
    if((first&0x80)==0||(first&0x70)!=0||(second&0x80)==0)throw new IOException("Unmasked, fragmented or reserved frame rejected");
    int length=second&127;
    if(length==126){length=(byteAt(in)<<8)|byteAt(in);if(length<126)throw new IOException("Noncanonical frame size");}
    else if(length==127)throw new IOException("Frame size too large");
    if(length>MAX_FRAME||((op&8)!=0&&length>125))throw new IOException("Frame size rejected");
    byte[] mask=new byte[4];for(int i=0;i<4;i++)mask[i]=(byte)byteAt(in);
    byte[] bytes=new byte[length];for(int i=0;i<length;i++)bytes[i]=(byte)(byteAt(in)^mask[i&3]);
    return new Frame(op,bytes);
  }
  private static void closeSocket(Socket socket){try{socket.close();}catch(IOException ignored){}}
  public void close(){closed=true;synchronized(sockets){for(Socket s:sockets)closeSocket(s);}watchdog.shutdownNow();commands.shutdownNow();stops.shutdownNow();}
}
