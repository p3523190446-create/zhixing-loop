package cn.zhixing.dashboard;
import android.os.SystemClock;
import org.json.*;
import java.io.*;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.*;

/** Local JPEG/index/telemetry journal, real Android monotonic receive times. */
public final class VideoRecorder {
  public interface StateSource{JSONObject get()throws Exception;}
  private static class Packet{byte[] bytes;long at;Packet(byte[] b,long t){bytes=b;at=t;}}
  private final GatewayService context;private final StateSource stateSource;private final File root;private final ArrayBlockingQueue<Packet> queue=new ArrayBlockingQueue<>(8);
  private volatile boolean active,finishing;private volatile String id,reason="",error;private volatile long frames,samples,bytes,dropped,started;private volatile double duration;
  private volatile boolean mp4Ready;private volatile long mp4Frames,mp4Dropped;
  public VideoRecorder(GatewayService value,StateSource source){context=value;stateSource=source;root=new File(value.getFilesDir(),"video");root.mkdirs();}
  public synchronized JSONObject status()throws JSONException{return new JSONObject().put("active",active).put("finishing",finishing).put("id",id==null?JSONObject.NULL:id).put("duration_s",Math.round((active||finishing?(SystemClock.elapsedRealtime()-started)/1000.0:duration)*10)/10.0).put("frames",frames).put("samples",samples).put("bytes",bytes).put("dropped_frames",dropped).put("video_ready",mp4Ready).put("video_format","video/mp4").put("mp4_frames",mp4Frames).put("mp4_dropped_frames",mp4Dropped).put("reason",reason).put("error",error==null?JSONObject.NULL:error);}
  public synchronized JSONObject start(JSONObject camera)throws Exception{
    if(active||finishing)throw new IllegalStateException("正在记录或保存");
    if(root.getUsableSpace()<64L*1024*1024)throw new IOException("手机存储不足64MB");
    String nextId=new SimpleDateFormat("yyyyMMdd-HHmmss",Locale.US).format(new Date())+"-"+UUID.randomUUID().toString().substring(0,6);
    File folder=folder(nextId);if(!folder.mkdirs())throw new IOException("无法创建记录");
    JSONObject meta=new JSONObject().put("id",nextId).put("started_at",new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX",Locale.US).format(new Date())).put("state","RECORDING").put("camera",camera).put("sync","Android monotonic reception times");
    // Fail before publishing active if this actual device cannot encode the requested mode.
    final Mp4Writer mp4=new Mp4Writer(new File(folder,"video.mp4"),camera.getInt("width"),camera.getInt("height"),camera.getInt("requested_fps"));
    try{write(new File(folder,"session.json"),meta);}catch(Exception failure){try{mp4.close();}catch(Exception ignored){}throw failure;}
    id=nextId;frames=samples=bytes=dropped=0;duration=0;error=null;reason="";queue.clear();
    mp4Ready=false;mp4Frames=mp4Dropped=0;started=SystemClock.elapsedRealtime();active=true;finishing=false;
    try{new Thread(()->record(folder,meta,mp4),"onboard-video-record").start();}
    catch(RuntimeException failure){active=false;finishing=false;try{mp4.close();}catch(Exception ignored){}error=failure.toString();meta.put("state","ERROR").put("error",error);write(new File(folder,"session.json"),meta);throw failure;}
    return status();
  }
  public synchronized JSONObject stop(String why){if(active){active=false;finishing=true;reason=why;}try{return status();}catch(JSONException e){return new JSONObject();}}
  public void frame(byte[] image,long at){if(!active||at<started)return;if(!queue.offer(new Packet(image,at)))dropped++;}
  private void record(File folder,JSONObject initial,Mp4Writer encoder){long lastSample=0,lastSync=SystemClock.elapsedRealtime(),lastFrame=started;try(Mp4Writer mp4=encoder;FileOutputStream video=new FileOutputStream(new File(folder,"video.mjpeg"));FileOutputStream index=new FileOutputStream(new File(folder,"frames.jsonl"));FileOutputStream telemetry=new FileOutputStream(new File(folder,"telemetry.jsonl"))){
    while(active||!queue.isEmpty()){
      Packet packet=queue.poll(50,TimeUnit.MILLISECONDS);long now=SystemClock.elapsedRealtime();
      if(now-lastSample>=1000){JSONObject state=stateSource.get();JSONObject row=new JSONObject().put("t",(now-started)/1000.0).put("state",state);telemetry.write((row.toString()+"\n").getBytes("UTF-8"));samples++;lastSample=now;}
      if(packet!=null){video.write(packet.bytes);JSONObject row=new JSONObject().put("t",(packet.at-started)/1000.0).put("offset",bytes).put("bytes",packet.bytes.length);index.write((row.toString()+"\n").getBytes("UTF-8"));bytes+=packet.bytes.length;frames++;lastFrame=packet.at;mp4.frame(packet.bytes,(packet.at-started)*1000);mp4Frames=mp4.encoded;mp4Dropped=mp4.dropped;}
      if(active&&now-lastFrame>=5000)stop("摄像头超过5秒未更新");
      if(active&&(now-started>=600000||bytes>=512L*1024*1024||root.getUsableSpace()<64L*1024*1024))stop(root.getUsableSpace()<64L*1024*1024?"存储不足":"单段时长或容量上限");
      if(now-lastSync>=1000){video.getFD().sync();index.getFD().sync();telemetry.getFD().sync();lastSync=now;}
    }
    video.getFD().sync();index.getFD().sync();telemetry.getFD().sync();
  }catch(Exception e){error=e.toString();active=false;finishing=true;context.audit("video_record_error",error);}
  finally{duration=(SystemClock.elapsedRealtime()-started)/1000.0;mp4Ready=error==null&&mp4Frames>0&&new File(folder,"video.mp4").length()>0;try{JSONObject meta=status();Iterator<String> keys=initial.keys();while(keys.hasNext()){String key=keys.next();if(!meta.has(key))meta.put(key,initial.get(key));}meta.put("state",error==null?"COMPLETE":"ERROR").put("active",false).put("finishing",false);write(new File(folder,"session.json"),meta);}catch(Exception e){mp4Ready=false;error="记录汇总保存失败："+e.toString();}finishing=false;}}
  private File folder(String name){if(name==null||!name.matches("[0-9]{8}-[0-9]{6}-[0-9a-f]{6}"))throw new IllegalArgumentException("记录编号错误");return new File(root,name);}
  private void write(File file,JSONObject object)throws Exception{File temporary=new File(file.getParentFile(),file.getName()+".tmp");try(FileOutputStream f=new FileOutputStream(temporary)){f.write(object.toString().getBytes("UTF-8"));f.getFD().sync();}if(!temporary.renameTo(file))throw new IOException("记录元数据保存失败");}
  private JSONObject object(File file)throws Exception{try(InputStream in=new FileInputStream(file);ByteArrayOutputStream bytes=new ByteArrayOutputStream()){byte[] b=new byte[4096];int n;while((n=in.read(b))>0){bytes.write(b,0,n);if(bytes.size()>16*1024*1024)throw new IOException("索引过大");}return new JSONObject(bytes.toString("UTF-8"));}}
  private JSONArray rows(File file)throws Exception{JSONArray result=new JSONArray();try(BufferedReader reader=new BufferedReader(new InputStreamReader(new FileInputStream(file),"UTF-8"))){String line;while((line=reader.readLine())!=null){if(line.length()>16384||result.length()>20000)throw new IOException("记录索引超限");result.put(new JSONObject(line));}}return result;}
  public JSONArray list()throws Exception{JSONArray list=new JSONArray();File[] dirs=root.listFiles();if(dirs==null)return list;Arrays.sort(dirs,(a,b)->b.getName().compareTo(a.getName()));for(File folder:dirs){if(!folder.isDirectory())continue;try{JSONObject meta=object(new File(folder,"session.json"));if(meta.optString("state").equals("RECORDING")&&!folder.getName().equals(id))meta.put("state","INTERRUPTED");list.put(meta);}catch(Exception ignored){}}return list;}
  public JSONObject replay(String name)throws Exception{if(name.equals(id)&&(active||finishing))throw new IllegalStateException("请先停止保存");File folder=folder(name);return new JSONObject().put("meta",object(new File(folder,"session.json"))).put("frames",rows(new File(folder,"frames.jsonl"))).put("samples",rows(new File(folder,"telemetry.jsonl")));}
  public byte[] frameAt(String name,int at)throws Exception{JSONArray indices=replay(name).getJSONArray("frames");if(at<0||at>=indices.length())throw new IllegalArgumentException("帧编号越界");JSONObject row=indices.getJSONObject(at);long offset=row.getLong("offset");int length=row.getInt("bytes");if(offset<0||length<=0||length>8*1024*1024)throw new IOException("帧索引异常");byte[] bytes=new byte[length];try(RandomAccessFile in=new RandomAccessFile(new File(folder(name),"video.mjpeg"),"r")){if(offset+length>in.length())throw new IOException("视频尾部不完整");in.seek(offset);in.readFully(bytes);}return bytes;}
  public File mp4(String name)throws Exception{
    if(name.equals(id)&&(active||finishing))throw new IllegalStateException("请先停止并保存录像");
    File folder=folder(name);JSONObject meta=object(new File(folder,"session.json"));File value=new File(folder,"video.mp4");
    if(!meta.optBoolean("video_ready")||!meta.optString("state").equals("COMPLETE")||!value.isFile()||value.length()==0)throw new IOException("这段记录没有已完成的MP4；原始回放仍可单独查看");
    return value;
  }
}
