package cn.zhixing.dashboard;
import android.graphics.SurfaceTexture;
import android.opengl.*;
import android.os.*;
import java.util.concurrent.*;

/** Drain camera preview buffers on a dedicated EGL thread, without a visible SurfaceView. */
public final class HeadlessSurface {
  private HandlerThread thread;private Handler handler;private SurfaceTexture texture;private EGLDisplay display;private EGLContext context;private EGLSurface surface;
  public HeadlessSurface(int width,int height)throws Exception{thread=new HandlerThread("camera-surface");thread.start();handler=new Handler(thread.getLooper());CountDownLatch ready=new CountDownLatch(1);final Throwable[] error={null};handler.post(()->{try{
    display=EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY);int[] version=new int[2];if(!EGL14.eglInitialize(display,version,0,version,1))throw new IllegalStateException("EGL初始化失败");
    EGLConfig[] configs=new EGLConfig[1];int[] count=new int[1];int[] options={EGL14.EGL_RED_SIZE,8,EGL14.EGL_GREEN_SIZE,8,EGL14.EGL_BLUE_SIZE,8,EGL14.EGL_SURFACE_TYPE,EGL14.EGL_PBUFFER_BIT,EGL14.EGL_RENDERABLE_TYPE,EGL14.EGL_OPENGL_ES2_BIT,EGL14.EGL_NONE};if(!EGL14.eglChooseConfig(display,options,0,configs,0,1,count,0)||count[0]<1)throw new IllegalStateException("EGL配置不可用");
    context=EGL14.eglCreateContext(display,configs[0],EGL14.EGL_NO_CONTEXT,new int[]{EGL14.EGL_CONTEXT_CLIENT_VERSION,2,EGL14.EGL_NONE},0);surface=EGL14.eglCreatePbufferSurface(display,configs[0],new int[]{EGL14.EGL_WIDTH,1,EGL14.EGL_HEIGHT,1,EGL14.EGL_NONE},0);if(!EGL14.eglMakeCurrent(display,surface,surface,context))throw new IllegalStateException("EGL上下文不可用");int[] names=new int[1];GLES20.glGenTextures(1,names,0);texture=new SurfaceTexture(names[0]);texture.setDefaultBufferSize(width,height);texture.setOnFrameAvailableListener(t->{try{t.updateTexImage();}catch(Exception ignored){}},handler);
  }catch(Throwable e){error[0]=e;}finally{ready.countDown();}});if(!ready.await(3000,TimeUnit.MILLISECONDS)||error[0]!=null){close();throw new IllegalStateException("外接画面输出初始化失败",error[0]);}}
  public SurfaceTexture texture(){return texture;}
  public void close(){if(handler!=null)handler.post(()->{try{if(texture!=null)texture.release();if(display!=null){EGL14.eglMakeCurrent(display,EGL14.EGL_NO_SURFACE,EGL14.EGL_NO_SURFACE,EGL14.EGL_NO_CONTEXT);if(surface!=null)EGL14.eglDestroySurface(display,surface);if(context!=null)EGL14.eglDestroyContext(display,context);EGL14.eglTerminate(display);}}finally{thread.quitSafely();}});}
}
