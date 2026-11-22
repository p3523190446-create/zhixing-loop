package cn.zhixing.dashboard;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.*;
import android.net.Uri;
import android.webkit.*;
import android.widget.*;

/** Local WebView and a small native connection/address header. */
public class MainActivity extends Activity {
  private GatewayService service;private boolean bound;private WebView browser;private TextView address;
  private ValueCallback<Uri[]> pictureChoice;private static final int PICK_PICTURE=7108;
  private final Handler handler=new Handler();private String opened="";
  private final ServiceConnection connection=new ServiceConnection(){public void onServiceConnected(ComponentName name,IBinder binder){service=((GatewayService.LocalBinder)binder).getService();refresh();}public void onServiceDisconnected(ComponentName name){service=null;}};
  public void onCreate(Bundle state){super.onCreate(state);getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);LinearLayout page=new LinearLayout(this);page.setOrientation(1);page.setBackgroundColor(0xff0e1618);
    LinearLayout row=new LinearLayout(this);Button connect=new Button(this);connect.setText("连接主控 · "+appVersion());connect.setTextSize(12);row.addView(connect,new LinearLayout.LayoutParams(0,-2,1));Button copy=new Button(this);copy.setText("复制网址");copy.setTextSize(12);row.addView(copy,new LinearLayout.LayoutParams(0,-2,1));page.addView(row);
    address=new TextView(this);address.setTextColor(0xffa9e4c3);address.setTextSize(11);address.setPadding(12,5,12,5);address.setTextIsSelectable(true);page.addView(address);
    browser=new WebView(this);browser.setBackgroundColor(0xff0e1618);browser.getSettings().setJavaScriptEnabled(true);browser.getSettings().setDomStorageEnabled(true);browser.getSettings().setAllowFileAccess(false);browser.getSettings().setSupportZoom(false);browser.getSettings().setBuiltInZoomControls(false);browser.getSettings().setDisplayZoomControls(false);browser.setWebViewClient(new WebViewClient());
    // This build is debuggable; the socket is local to ADB, not a network server.
    WebView.setWebContentsDebuggingEnabled(true);
    browser.setWebChromeClient(new WebChromeClient(){
      public boolean onConsoleMessage(ConsoleMessage message){if(service!=null)service.audit("web_console",message.messageLevel()+" "+message.lineNumber()+" "+message.message());return true;}
      public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
        if(pictureChoice!=null)pictureChoice.onReceiveValue(null);pictureChoice=callback;
        Intent pick=new Intent(Intent.ACTION_OPEN_DOCUMENT);pick.setType("image/*");pick.addCategory(Intent.CATEGORY_OPENABLE);
        try{startActivityForResult(pick,PICK_PICTURE);}catch(ActivityNotFoundException error){pictureChoice.onReceiveValue(null);pictureChoice=null;Toast.makeText(MainActivity.this,"没有可用的照片选择器",Toast.LENGTH_SHORT).show();}return true;
      }
    });page.addView(browser,new LinearLayout.LayoutParams(-1,0,1));setContentView(page);
    connect.setOnClickListener(v->startActivity(new Intent(this,DiagnosticActivity.class)));
    copy.setOnClickListener(v->{if(service!=null){((android.content.ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("调试台地址",service.remoteAddress()));Toast.makeText(this,"地址已复制，发给主力手机打开",Toast.LENGTH_SHORT).show();}});
    startForegroundService(new Intent(this,GatewayService.class));bound=bindService(new Intent(this,GatewayService.class),connection,BIND_AUTO_CREATE);selfCheck(getIntent());
    if(checkSelfPermission(android.Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{android.Manifest.permission.CAMERA},7);
  }
  private String appVersion(){try{return getPackageManager().getPackageInfo(getPackageName(),0).versionName;}catch(Exception ignored){return "unknown";}}
    private void refresh(){if(service==null)return;String base=service.localAddress();if(!base.equals(opened)){opened=base;browser.loadUrl(base+"mobile");}address.setText(service.remoteAddress()+"\n基础车控在本手机；大模型看图使用电脑服务");}
  private final Runnable tick=new Runnable(){public void run(){refresh();handler.postDelayed(this,1500);}};
  public void onResume(){super.onResume();handler.post(tick);if(browser!=null)browser.onResume();}
  public void onPause(){handler.removeCallbacks(tick);if(browser!=null)browser.onPause();super.onPause();}
  public void onDestroy(){handler.removeCallbacks(tick);if(pictureChoice!=null){pictureChoice.onReceiveValue(null);pictureChoice=null;}if(bound)unbindService(connection);if(browser!=null)browser.destroy();super.onDestroy();}
  protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==PICK_PICTURE&&pictureChoice!=null){pictureChoice.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result,data));pictureChoice=null;}}
  private void selfCheck(Intent intent){if(intent!=null&&intent.getBooleanExtra("imu_self_check",false))new Thread(()->ImuTelemetrySelfCheck.run(getFilesDir()),"imu-readonly-check").start();if(intent!=null&&intent.getBooleanExtra("local_self_check",false))new Thread(()->ControlSelfCheck.run(getFilesDir()),"control-unit-check").start();}
  public void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);selfCheck(intent);}
}
