package cn.zhixing.localbench;
import android.app.*;
import android.os.*;
import android.graphics.Color;
import android.view.*;
import android.widget.*;
import java.io.*;
import org.json.*;

/** Standalone, permission-free offline measurement; no camera/controller/network. */
public final class MainActivity extends Activity {
  private TextView status,results;private Button start;private volatile boolean running;
  public void onCreate(Bundle state){
    super.onCreate(state);
    ScrollView scroll=new ScrollView(this);LinearLayout content=new LinearLayout(this);content.setOrientation(1);content.setPadding(22,26,22,26);content.setBackgroundColor(Color.rgb(239,245,247));scroll.addView(content);setContentView(scroll);
    TextView title=new TextView(this);title.setText("知行回路 · 手机本地测评");title.setTextSize(23);title.setTextColor(Color.rgb(15,62,68));content.addView(title);
    TextView note=new TextView(this);note.setText("计算全部在本手机。测试使用内置旧图，不打开摄像头、不连接主控、不访问网络。数值不包含实际取图、显示或车辆动作。\n");note.setTextSize(16);note.setPadding(0,18,0,12);content.addView(note);
    start=new Button(this);start.setText("开始本机测试");content.addView(start);
    status=new TextView(this);status.setText("准备好后点击测试；拔掉电脑线也能运行。");status.setTextSize(16);status.setPadding(0,14,0,14);content.addView(status);
    results=new TextView(this);results.setTextSize(16);results.setTextIsSelectable(true);content.addView(results);
    start.setOnClickListener(v->runBench());
    try{File saved=new File(getFilesDir(),"result.json");if(saved.exists())show(new JSONObject(read(saved)));}catch(Exception ignored){}
    if(getIntent().getBooleanExtra("auto_run",false))runBench();
  }
  private String read(File file)throws Exception{
    try(InputStream in=new FileInputStream(file);ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[4096];int n;while((n=in.read(b))>0)out.write(b,0,n);return new String(out.toByteArray(),"UTF-8");}
  }
  private void asset(String name)throws Exception{
    File outFile=new File(getFilesDir(),name);
    if(outFile.exists())return;
    try(InputStream in=getAssets().open(name);OutputStream out=new FileOutputStream(outFile)){byte[] b=new byte[65536];int n;while((n=in.read(b))>0)out.write(b,0,n);}
  }
  private void runBench(){
    if(running)return;running=true;start.setEnabled(false);status.setText("正在手机本机计算，请稍候…");
    new Thread(()->{try{
      for(String name:new String[]{"zx_local_bench","yolov8n.ncnn.param","yolov8n.ncnn.bin","frame.rgb"})asset(name);
      File executable=new File(getFilesDir(),"zx_local_bench");if(!executable.setExecutable(true,true))throw new IOException("无法执行本地测试");
      File error=new File(getFilesDir(),"native-stderr.log");
      java.lang.Process process=new ProcessBuilder(executable.getAbsolutePath(),getFilesDir().getAbsolutePath()).redirectError(error).start();
      ByteArrayOutputStream data=new ByteArrayOutputStream();
      try(InputStream in=process.getInputStream()){byte[] b=new byte[4096];int n;while((n=in.read(b))>0){if(data.size()+n>65536)throw new IOException("测试结果异常");data.write(b,0,n);}}
      int code=process.waitFor();if(code!=0)throw new IOException("原生计算返回 "+code+"；"+read(error));
      String raw=new String(data.toByteArray(),"UTF-8");JSONObject report=new JSONObject(raw);
      try(OutputStream out=new FileOutputStream(new File(getFilesDir(),"result.json"))){out.write(raw.getBytes("UTF-8"));}
      runOnUiThread(()->{show(report);status.setText("完成：此结果由本手机独立计算。真实相机链路尚待测试。");});
    }catch(Exception error){runOnUiThread(()->status.setText("测试未完成："+error.toString()));}
    finally{running=false;runOnUiThread(()->start.setEnabled(true));}},"phone-local-benchmark").start();
  }
  private void show(JSONObject report){try{
    StringBuilder text=new StringBuilder();JSONObject color=report.getJSONObject("color_pipeline");
    text.append("简单颜色/图像处理\n中位 ").append(color.getDouble("median_ms")).append(" ms\n\nYOLOv8n 本地 CPU\n");
    JSONArray models=report.getJSONArray("models");
    for(int i=0;i<models.length();i++){JSONObject item=models.getJSONObject(i);text.append(item.getInt("target_size")).append(" 输入 · ").append(item.getInt("threads")).append("线程\n中位 ").append(item.getDouble("median_ms")).append(" ms / P95 ").append(item.getDouble("p95_ms")).append(" ms\n本图检测数 ").append(item.getInt("last_detections")).append("\n\n");}
    text.append("输入缩小会改变检测结果。不要把推理时间换算成整车实测帧率。\n测试结果保存在本手机，可再次点击复测。");results.setText(text.toString());
  }catch(Exception error){status.setText("结果解析失败："+error.toString());}}
}
