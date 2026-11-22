"""Host checks for real mode selection, USB classification and packaged bridge."""
from pathlib import Path
import hashlib,json,os,subprocess,tempfile,zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
OUT=ROOT/'output/onboard_dashboard/camera-compat-20261026'
CACHE=Path.home()/'.cache/zhixing-android-tools'
jdk=Path(os.environ.get('JAVA_HOME',r'C:\Program Files\BellSoft\LibericaJDK-17'))/'bin'
android=next(CACHE.glob('platform-33-ext3_r03/**/android.jar'))
work=OUT/'host-checks';work.mkdir(exist_ok=True)
sources={
'android/hardware/usb/UsbInterface.java':'''package android.hardware.usb; public class UsbInterface { private final int c; public UsbInterface(int v){c=v;} public int getInterfaceClass(){return c;} public int getId(){return 0;} public int getAlternateSetting(){return 0;} public int getInterfaceSubclass(){return 0;} public int getEndpointCount(){return 0;} }''',
'android/hardware/usb/UsbDevice.java':'''package android.hardware.usb; public class UsbDevice { private final int v,p,c;private final UsbInterface[] i;public UsbDevice(int v,int p,int c,UsbInterface... i){this.v=v;this.p=p;this.c=c;this.i=i;}public int getVendorId(){return v;}public int getProductId(){return p;}public int getDeviceClass(){return c;}public int getInterfaceCount(){return i.length;}public UsbInterface getInterface(int n){return i[n];} }''',
'android/hardware/usb/UsbManager.java':'''package android.hardware.usb;public class UsbManager {public boolean hasPermission(UsbDevice d){return false;} }''',
'cn/zhixing/dashboard/CompatChecks.java':'''package cn.zhixing.dashboard;
import java.util.*;import android.hardware.usb.*;
public class CompatChecks {
 static int checks=0;static void check(boolean value){checks++;if(!value)throw new AssertionError("check "+checks);}
 static CameraModes.Mode mode(int t,int w,int h,Integer... fps){return new CameraModes.Mode(t,w,h,Arrays.asList(fps));}
 public static void main(String[] args){
  CameraModes.Mode original=mode(7,640,480,15,30),borrowed=mode(5,1920,1536,30);
  check(CameraModes.choose(Arrays.asList(original),640,480,30)==original);
  check(CameraModes.choose(Arrays.asList(borrowed),640,480,15)==borrowed);
  check(CameraModes.fps(borrowed,15)==30); // Never invent an unsupported USB rate.
  check(CameraModes.fps(original,20)==15);
  check(CameraModes.fps(mode(7,640,480,30,5,15),10)==5);
  check(CameraModes.choose(Arrays.asList(mode(16,640,480,30)),640,480,30)==null);
  check(CameraModes.choose(Arrays.asList(mode(5,641,480,30)),640,480,30)==null);
  check(CameraModes.choose(Arrays.asList(mode(7,640,480,0,-1)),640,480,30)==null);
  CameraModes.Mode lower=mode(7,640,480,15);
  check(CameraModes.choose(Arrays.asList(mode(7,320,240,15),lower),1280,720,15)==lower);
  check(CameraModes.choose(Arrays.asList(mode(5,640,480,30),original),640,480,30)==original);
  check(UsbCameraInfo.camera(new UsbDevice(0x145f,0x02ec,0)));
  check(UsbCameraInfo.camera(new UsbDevice(0x04b4,0x00c3,0)));
  check(UsbCameraInfo.camera(new UsbDevice(1,2,0,new UsbInterface(14))));
  check(!UsbCameraInfo.camera(new UsbDevice(0x1a86,0xfe0c,14,new UsbInterface(14))));
  check(!UsbCameraInfo.camera(new UsbDevice(1,2,3,new UsbInterface(3))));
  check(UsbCameraInfo.label(new UsbDevice(0x04b4,0x00c3,0)).contains("USB031"));
  System.out.println("PASS "+checks+" mode and USB classification checks; host fixtures only");
 }
}'''}
paths=[]
for name,data in sources.items():
    p=work/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data,encoding='utf-8');paths.append(p)
classes=work/'classes';classes.mkdir(exist_ok=True)
subprocess.run([str(jdk/'javac.exe'),'-encoding','UTF-8','--release','8','-cp',str(android),'-d',str(classes),*[str(p) for p in paths],str(HERE/'android/CameraModes.java'),str(HERE/'android/UsbCameraInfo.java')],check=True)
host=subprocess.check_output([str(jdk/'java.exe'),'-cp',str(classes)+os.pathsep+str(android),'cn.zhixing.dashboard.CompatChecks'],text=True)
bridge=OUT/'native/libUVCCamera.so'
readelf=next(CACHE.glob('android-ndk-r29-windows/**/llvm-readelf.exe'))
symbols=subprocess.check_output([str(readelf),'--dyn-syms','--wide',str(bridge)],text=True)
assert any('UND' in line and 'uvc_any2rgbx' in line for line in symbols.splitlines())
assert not any('UND' in line and 'uvc_yuyv2rgbx' in line for line in symbols.splitlines())
uvc=ROOT/'tmp/uvc-android/aar/jni/arm64-v8a/libuvc.so'
uvc_symbols=subprocess.check_output([str(readelf),'--dyn-syms','--wide',str(uvc)],text=True)
for symbol in ['uvc_any2rgbx','uvc_uyvy2rgbx','uvc_yuyv2rgbx']:
    assert any('UND' not in line and line.rstrip().endswith(symbol) for line in uvc_symbols.splitlines()),symbol
with zipfile.ZipFile(OUT/'zhixing-dashboard.apk') as apk:
    assert apk.read('lib/arm64-v8a/libUVCCamera.so')==bridge.read_bytes()
    for name in ['libusb1.0.so','libuvc.so','libyuv.so','libjpeg-turbo212.so']:
        assert apk.read('lib/arm64-v8a/'+name)==(uvc.parent/name).read_bytes(),name
    assert b'createFramePump' not in apk.read('assets/web/assets/features/camera.js')
report=dict(host=host.strip(),native_dispatch='PASS: patched bridge calls format-aware converter; cached libuvc exports both pixel converters',apk='PASS: exact patched bridge and unchanged dependencies',scope='HOST_FIXTURES_AND_PACKAGE_ONLY; no phone enumeration/capture acceptance')
(OUT/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
