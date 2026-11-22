package cn.zhixing.carconsole;
import android.content.*;
import android.os.*;
import org.json.*;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

/** Android-owned assets/API. Never opens USB or forwards client UART strings. */
public final class CarWebServer {
    public static final int PORT=8772;private final TelemetryService service;
    private final String base;private ServerSocket listener;private volatile boolean closing;
    private final ThreadPoolExecutor pool=new ThreadPoolExecutor(2,4,30,TimeUnit.SECONDS,new ArrayBlockingQueue<Runnable>(16));
    public CarWebServer(TelemetryService s){service=s;SharedPreferences p=s.getSharedPreferences("car-web",0);String token=p.getString("token",null);if(token==null){token=UUID.randomUUID().toString().replace("-","");p.edit().putString("token",token).apply();}base="/"+token;}
    public String local(){return "http://127.0.0.1:"+PORT+base+"/mobile";}
    public JSONArray urls(){JSONArray a=new JSONArray();try{Enumeration<NetworkInterface> n=NetworkInterface.getNetworkInterfaces();while(n.hasMoreElements()){NetworkInterface i=n.nextElement();if(!i.isUp())continue;Enumeration<InetAddress> ips=i.getInetAddresses();while(ips.hasMoreElements()){InetAddress ip=ips.nextElement();if(ip instanceof Inet4Address&&!ip.isLoopbackAddress()&&!ip.isLinkLocalAddress())a.put("http://"+ip.getHostAddress()+":"+PORT+base+"/mobile");}}}catch(Exception ignored){}return a;}
    public void start()throws IOException{listener=new ServerSocket();listener.setReuseAddress(true);listener.bind(new InetSocketAddress("0.0.0.0",PORT),8);new Thread(new Runnable(){public void run(){while(!closing)try{final Socket s=listener.accept();s.setSoTimeout(4000);try{pool.execute(new Runnable(){public void run(){handle(s);}});}catch(RejectedExecutionException e){s.close();}}catch(IOException e){if(!closing)android.util.Log.e("CarWeb","accept failed",e);}}},"car-web-listener").start();}
    public void close(){closing=true;try{if(listener!=null)listener.close();}catch(IOException ignored){}pool.shutdownNow();}
    private String line(InputStream in,int max)throws IOException{ByteArrayOutputStream b=new ByteArrayOutputStream();int c;while((c=in.read())!=-1){if(c=='\n')return new String(b.toByteArray(),StandardCharsets.US_ASCII).replace("\r","");if(b.size()>=max)throw new IOException("Header too long");b.write(c);}return b.size()==0?null:new String(b.toByteArray(),StandardCharsets.US_ASCII);}
    private byte[] asset(String path)throws IOException{try(InputStream in=service.getAssets().open("carweb/"+path)){ByteArrayOutputStream b=new ByteArrayOutputStream();byte[] buf=new byte[4096];int n;while((n=in.read(buf))!=-1)b.write(buf,0,n);return b.toByteArray();}}
    private void send(Socket socket,int code,Object value,String type)throws IOException{byte[] bytes=value instanceof byte[]?(byte[])value:value.toString().getBytes(StandardCharsets.UTF_8);String head="HTTP/1.1 "+code+" "+(code==200?"OK":"Error")+"\r\nContent-Type: "+type+"\r\nContent-Length: "+bytes.length+"\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n";OutputStream out=socket.getOutputStream();out.write(head.getBytes(StandardCharsets.US_ASCII));out.write(bytes);out.flush();}
    private JSONObject error(String msg)throws JSONException{JSONObject o=new JSONObject();o.put("error",msg);return o;}
    private void handle(Socket socket){try{
        InputStream in=socket.getInputStream();String first=line(in,2048);if(first==null)return;String[] request=first.split(" ");if(request.length!=3)throw new IOException("Bad request");String method=request[0],path=request[1].split("\\?",2)[0];
        Map<String,String> headers=new HashMap<>();int total=0;String h;while((h=line(in,4096))!=null&&!h.isEmpty()){total+=h.length();if(total>8192)throw new IOException("Headers too long");int colon=h.indexOf(':');if(colon>0)headers.put(h.substring(0,colon).toLowerCase(Locale.US),h.substring(colon+1).trim());}
        String host=headers.get("host"),localHost=socket.getLocalAddress().getHostAddress()+":"+PORT;
        if(host==null||(!host.equals(localHost)&&!host.equals("localhost:"+PORT))){android.util.Log.w("CarWeb","Host mismatch "+host+" local "+localHost);send(socket,403,error("请使用车载端显示的地址"),"application/json; charset=utf-8");return;}
        if(!path.startsWith(base+"/")){send(socket,404,error("地址不存在"),"application/json; charset=utf-8");return;}
        String route=path.substring(base.length()+1);
        if(method.equals("GET")&&!route.startsWith("api/")){
            if(route.equals("")||route.equals("mobile")||route.equals("desktop")){String html=new String(asset("index.html"),StandardCharsets.UTF_8).replace("<body>","<body data-base=\""+base+"\">").replace("href=\"assets/","href=\""+base+"/assets/").replace("src=\"assets/","src=\""+base+"/assets/");send(socket,200,html.getBytes(StandardCharsets.UTF_8),"text/html; charset=utf-8");return;}
            if(route.startsWith("assets/")&&route.matches("assets/[A-Za-z0-9_/-]+\\.(js|css)")){send(socket,200,asset(route),route.endsWith(".js")?"text/javascript; charset=utf-8":"text/css; charset=utf-8");return;}
            send(socket,404,error("页面不存在"),"application/json; charset=utf-8");return;
        }
        if(!route.startsWith("api/")){send(socket,405,error("操作未开放"),"application/json; charset=utf-8");return;}
        String api=route.substring(4);JSONObject body=new JSONObject();
        if(method.equals("POST")){
            if(!("http://"+host).equals(headers.get("origin"))||!headers.getOrDefault("content-type","").startsWith("application/json")||headers.containsKey("transfer-encoding")){send(socket,403,error("请从当前网页操作"),"application/json; charset=utf-8");return;}
            int n=Integer.parseInt(headers.getOrDefault("content-length","0"));if(n<=0||n>512)throw new IOException("Bad body length");byte[] b=new byte[n];int at=0;while(at<n){int read=in.read(b,at,n-at);if(read<0)throw new IOException("Partial body");at+=read;}body=new JSONObject(new String(b,StandardCharsets.UTF_8));
            service.webEvent(api,body);
        }
        Object value=null;int code=200;
        if(method.equals("GET")){
            if(api.equals("status"))value=service.webStatus();
            else if(api.equals("ui/info")){JSONObject o=new JSONObject();o.put("demo",false);o.put("source","车载安卓P7主控通信");JSONObject c=new JSONObject();c.put("raw_record",true);c.put("gimbal",false);c.put("camera",false);c.put("vehicle_motion",false);o.put("capabilities",c);o.put("remote_urls",urls());value=o;}
            else if(api.equals("record/status"))value=service.webRecordStatus();
            else if(api.equals("record/list"))value=recordList();
            else if(api.matches("record/[0-9]{13}-[0-9a-f]{8}/data"))value=recordData(api.split("/")[1]);
            else if(api.equals("camera/status")){JSONObject o=new JSONObject();o.put("running",false);o.put("valid",false);o.put("supported",false);o.put("error","外接相机尚未接入车载网页");value=o;}
            else {code=404;value=error("接口不存在");}
        }else if(method.equals("POST")){
            if(api.equals("record/start")){if(!body.keys().hasNext()){service.beginFromWeb();value=service.webRecordStatus();}else {code=400;value=error("开始记录不接受额外参数");}}
            else if(api.equals("record/stop")){service.requestStop("WEB_USER_STOP");value=service.webRecordStatus();}
            else {code=501;value=error(api.startsWith("gimbal/")?"P7云台控制尚未接入；当前不会发送动作":api.startsWith("camera/")?"相机尚未接入车载网页":"操作未开放");}
        }else {code=405;value=error("请求方式不支持");}
        send(socket,code,value,"application/json; charset=utf-8");
    }catch(Exception e){try{send(socket,503,error(e.getMessage()==null?"请求处理失败":e.getMessage()),"application/json; charset=utf-8");}catch(Exception ignored){}android.util.Log.w("CarWeb","request failed: "+e.getClass().getSimpleName());}finally{try{socket.close();}catch(IOException ignored){}}}
    private File session(String id)throws IOException{if(!id.matches("[0-9]{13}-[0-9a-f]{8}"))throw new IOException("Invalid record id");File f=new File(service.getFilesDir(),"sessions/"+id);if(!f.isDirectory())throw new IOException("记录不存在");return f;}
    private JSONObject json(File file)throws Exception{try(FileInputStream in=new FileInputStream(file)){if(file.length()>65536)throw new IOException("Metadata too large");ByteArrayOutputStream b=new ByteArrayOutputStream();byte[] buf=new byte[4096];int n;while((n=in.read(buf))!=-1)b.write(buf,0,n);return new JSONObject(new String(b.toByteArray(),StandardCharsets.UTF_8));}}
    private JSONObject meta(File f)throws Exception{JSONObject start=json(new File(f,"session.json"));JSONObject o=new JSONObject();o.put("id",f.getName());o.put("started_at",new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss",Locale.CHINA).format(new Date(start.getLong("started_wall_ms"))));File endFile=new File(f,"result.json");boolean active=service.isBusy()&&f.getName().equals(service.session());JSONObject end=endFile.exists()?json(endFile):null;o.put("state",active?"RECORDING":end==null?"INTERRUPTED":end.optBoolean("clean_close")?"SAVED":"ERROR");o.put("duration_s",end==null?0:Math.max(0,end.getLong("ended_wall_ms")-start.getLong("started_wall_ms"))/1000.0);o.put("samples",end==null?0:end.optLong("cycles"));o.put("frames",0);return o;}
    private JSONArray recordList()throws Exception{JSONArray a=new JSONArray();File[] files=new File(service.getFilesDir(),"sessions").listFiles();if(files!=null){Arrays.sort(files,Collections.reverseOrder());int n=0;for(File f:files)if(f.isDirectory()&&f.getName().matches("[0-9]{13}-[0-9a-f]{8}")&&n++<100)try{a.put(meta(f));}catch(Exception ignored){}}return a;}
    private JSONObject recordData(String id)throws Exception{File f=session(id);JSONObject metadata=meta(f);if(metadata.getString("state").equals("RECORDING"))throw new IOException("请先停止保存，再打开回放");ArrayDeque<JSONObject> samples=new ArrayDeque<>();long first=-1;try(BufferedReader reader=new BufferedReader(new InputStreamReader(new FileInputStream(new File(f,"events.jsonl")),StandardCharsets.UTF_8))){String line;while((line=reader.readLine())!=null){JSONObject e;try{e=new JSONObject(line);}catch(JSONException ex){break;}if(first<0)first=e.getLong("elapsed_ns");if(!e.optString("event").equals("sample_complete"))continue;JSONObject fields=e.getJSONObject("fields");Map<String,String> m=new HashMap<>();Iterator<String> keys=fields.keys();while(keys.hasNext()){String k=keys.next();m.put(k,fields.getString(k));}JSONObject sample=new JSONObject();sample.put("t",(e.getLong("elapsed_ns")-first)/1e9);sample.put("state",WebState.decode(m,true,0,e.getLong("wall_ms")));samples.add(sample);if(samples.size()>1200)samples.removeFirst();}}
        JSONObject result=new JSONObject();result.put("meta",metadata);result.put("frames",new JSONArray());result.put("samples",new JSONArray(samples));result.put("video_available",false);return result;}
}
