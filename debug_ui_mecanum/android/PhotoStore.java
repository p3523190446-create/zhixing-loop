package cn.zhixing.dashboard;

import java.io.*;
import java.text.SimpleDateFormat;
import java.util.*;
import org.json.*;

/** A snapshot keeps the captured frame identity and its reception timestamp. */
public final class PhotoStore {
  private final GatewayService context;
  private final File root;
  public PhotoStore(GatewayService context){this.context=context;root=new File(context.getFilesDir(),"photos");root.mkdirs();}
  private File file(String id,String suffix){
    if(id==null||!id.matches("[0-9]{8}-[0-9]{6}-[0-9a-f]{6}"))throw new IllegalArgumentException("照片编号错误");
    return new File(root,id+suffix);
  }
  public synchronized JSONObject capture(ExternalCamera.Capture frame,JSONObject state)throws Exception{
    if(root.getUsableSpace()<64L*1024*1024)throw new IOException("手机存储不足64MB");
    String id=new SimpleDateFormat("yyyyMMdd-HHmmss",Locale.US).format(new Date())+"-"+UUID.randomUUID().toString().substring(0,6);
    File photo=file(id,".jpg"),metadata=file(id,".json");
    JSONObject info=new JSONObject().put("id",id).put("wall_ms",System.currentTimeMillis())
      .put("frame_seq",frame.sequence).put("frame_received_ms",frame.receivedAt)
      .put("width",frame.width).put("height",frame.height).put("bytes",frame.bytes.length)
      .put("source","ANDROID_EXTERNAL_UVC").put("state",state);
    try{
      try(FileOutputStream out=new FileOutputStream(photo)){out.write(frame.bytes);out.getFD().sync();}
      try(FileOutputStream out=new FileOutputStream(metadata)){out.write(info.toString().getBytes("UTF-8"));out.getFD().sync();}
    }catch(Exception error){context.audit("photo_save_error",error.toString());throw error;}
    context.audit("photo_saved",id+" frame_seq="+frame.sequence);return info;
  }
  public synchronized JSONArray list()throws Exception{
    File[] files=root.listFiles((dir,name)->name.endsWith(".json"));JSONArray result=new JSONArray();
    if(files==null)return result;Arrays.sort(files,(a,b)->b.getName().compareTo(a.getName()));
    for(int i=0;i<files.length&&result.length()<100;i++)try{
      if(files[i].length()>65536)continue;
      try(BufferedReader in=new BufferedReader(new InputStreamReader(new FileInputStream(files[i]),"UTF-8"))){
        String line=in.readLine();JSONObject info=new JSONObject(line);
        if(file(info.getString("id"),".jpg").isFile()){info.remove("state");result.put(info);}
      }
    }catch(Exception error){context.audit("photo_list_skipped",files[i].getName());}
    return result;
  }
  public File image(String id)throws IOException{File value=file(id,".jpg");if(!value.isFile())throw new FileNotFoundException("照片不存在");return value;}
}
