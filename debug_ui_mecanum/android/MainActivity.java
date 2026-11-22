package cn.zhixing.dashboard;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.*;
import android.webkit.*;
import android.widget.*;

/** Local WebView and a small native connection/address header. */
public class MainActivity extends Activity {
  private GatewayService service;private boolean bound;private WebView browser;private TextView address;
  private final Handler handler=new Handler();private String opened="";
  private final ServiceConnection connection=new ServiceConnection(){public void onServiceConnected(ComponentName name,IBinder binder){service=((GatewayService.LocalBinder)binder).getService();refresh();}public void onServiceDisconnected(ComponentName name){service=null;}};
  public void onCreate(Bundle state){super.onCreate(state);LinearLayout page=new LinearLayout(this);page.setOrientation(1);page.setBackgroundColor(0xff0e1618);
    LinearLayout row=new LinearLayout(this);Button connect=new Button(this);connect.setText("连接主控 · "+appVersion());connect.setTextSize(12);row.addView(connect,new LinearLayout.LayoutParams(0,-2,1));Button copy=new Button(this);copy.setText("复制网址");copy.setTextSize(12);row.addView(copy,new LinearLayout.LayoutParams(0,-2,1));page.addView(row);
    address=new TextView(this);address.setTextColor(0xffa9e4c3);address.setTextSize(11);address.setPadding(12,5,12,5);address.setTextIsSelectable(true);page.addView(address);
    browser=new WebView(this);browser.setBackgroundColor(0xff0e1618);browser.getSettings().setJavaScriptEnabled(true);browser.getSettings().setDomStorageEnabled(true);browser.getSettings().setAllowFileAccess(false);browser.getSettings().setSupportZoom(false);browser.getSettings().setBuiltInZoomControls(false);browser.getSettings().setDisplayZoomControls(false);browser.setWebViewClient(new WebViewClient());
    // This build is debuggable; the socket is local to ADB, not a network server.
    WebView.setWebContentsDebuggingEnabled(true);
    browser.setWebChromeClient(new WebChromeClient(){public boolean onConsoleMessage(ConsoleMessage message){if(service!=null)service.audit("web_console",message.messageLevel()+" "+message.lineNumber()+" "+message.message());return true;}});page.addView(browser,new LinearLayout.LayoutParams(-1,0,1));setContentView(page);
    connect.setOnClickListener(v->startActivity(new Intent(this,DiagnosticActivity.class)));
    copy.setOnClickListener(v->{if(service!=null){((android.content.ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("调试台地址",service.remoteAddress()));Toast.makeText(this,"地址已复制，发给主力手机打开",Toast.LENGTH_SHORT).show();}});
    startForegroundService(new Intent(this,GatewayService.class));bound=bindService(new Intent(this,GatewayService.class),connection,BIND_AUTO_CREATE);selfCheck(getIntent());
    if(checkSelfPermission(android.Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{android.Manifest.permission.CAMERA},7);
  }
  private String appVersion(){try{return getPackageManager().getPackageInfo(getPackageName(),0).versionName;}catch(Exception ignored){return "unknown";}}
    private void refresh(){if(service==null)return;String base=service.localAddress();if(!base.equals(opened)){opened=base;browser.loadUrl(base+"mobile");}address.setText(service.remoteAddress()+"\n网页服务在本手机，演示无需电脑");}
  private final Runnable tick=new Runnable(){public void run(){refresh();handler.postDelayed(this,1500);}};
  public void onResume(){super.onResume();handler.post(tick);if(browser!=null)browser.onResume();}
  public void onPause(){handler.removeCallbacks(tick);if(browser!=null)browser.onPause();super.onPause();}
  public void onDestroy(){handler.removeCallbacks(tick);if(bound)unbindService(connection);if(browser!=null)browser.destroy();super.onDestroy();}
  private void selfCheck(Intent intent){if(intent!=null&&intent.getBooleanExtra("local_self_check",false))new Thread(()->ControlSelfCheck.run(getFilesDir()),"control-unit-check").start();}
  public void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);selfCheck(intent);}
}
