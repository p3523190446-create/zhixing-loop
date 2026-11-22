"""Package the same desktop/mobile modules into an independent onboard Android host."""
from pathlib import Path
import os,sys,zipfile,json,hashlib,shutil,re
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
sys.path.insert(0,str(ROOT/'知行回路软件/phone_vision'))
from build import CACHE,unique,run
work=Path(os.environ.get('ZX_DASHBOARD_BUILD_WORK',str(Path.home()/'.cache/zhixing-dashboard-build')))
work.mkdir(parents=True,exist_ok=True)
classes=work/'classes'
if classes.exists():
    # Restrict cleanup to this private compiler output directory.
    assert classes.resolve().is_relative_to(work.resolve())
    shutil.rmtree(classes)
classes.mkdir()
dex=work/'dex';dex.mkdir(exist_ok=True)
deps=ROOT/'tmp/uvc-android'
compat_bridge=Path(os.environ.get('ZX_DASHBOARD_UVC_BRIDGE',str(ROOT/'output/onboard_dashboard/camera-compat-20261026/native/libUVCCamera.so')))
if not compat_bridge.is_file():
    raise RuntimeError('Run debug_ui/build_uvc_compat.py first: UYVY support requires the patched native preview bridge')
core=work/'uvc-core.jar'
with zipfile.ZipFile(deps/'aar/classes.jar') as src,zipfile.ZipFile(core,'w') as dst:
    for name in src.namelist():
        if (name.startswith('com/serenegiant/usb/') and not name.startswith('com/serenegiant/usb/CameraDialog')) or name.startswith('com/serenegiant/utils/HandlerThreadHandler') or name=='com/serenegiant/uvccamera/BuildConfig.class':dst.writestr(name,src.read(name))
android=unique('platform-33-ext3_r03/**/android.jar')
aapt=unique('build-tools_r35_windows/**/aapt2.exe');d8=unique('build-tools_r35_windows/**/lib/d8.jar')
signer=unique('build-tools_r35_windows/**/lib/apksigner.jar');align=unique('build-tools_r35_windows/**/zipalign.exe')
jdk=Path(os.environ['JAVA_HOME'])/'bin'
run([jdk/'javac.exe','-encoding','UTF-8','--release','8','-classpath',str(android)+os.pathsep+str(core),'-d',classes,*sorted((HERE/'android').glob('*.java'))])
jar=work/'classes.jar'
with zipfile.ZipFile(jar,'w') as dst:
    for p in classes.rglob('*.class'):dst.write(p,p.relative_to(classes).as_posix())
run([jdk/'java.exe','-cp',d8,'com.android.tools.r8.D8','--min-api','26','--lib',android,'--output',dex,jar,core])
base=work/'base.apk';run([aapt,'link','-I',android,'--manifest',HERE/'android/AndroidManifest.xml','-o',base])
with zipfile.ZipFile(base,'a') as dst:
    dst.write(dex/'classes.dex','classes.dex',compress_type=zipfile.ZIP_DEFLATED)
    dst.write(ROOT/'tmp/uvc-compat-1.0.13/LICENSE','assets/notices/UVCAndroid-1.0.13-LICENSE.txt',compress_type=zipfile.ZIP_DEFLATED)
    dst.writestr('assets/notices/UVCAndroid-CHANGES.txt','Based on shiyinghan/UVCAndroid 1.0.13 (6018c7f20238832929cf61427427bb7828056260). Modified uncompressed preview dispatch from uvc_yuyv2rgbx to uvc_any2rgbx for YUYV/UYVY compatibility. Original MJPEG path retained.\n')
    dst.write(HERE/'index.html','assets/web/index.html',compress_type=zipfile.ZIP_DEFLATED)
    for p in (HERE/'assets').rglob('*'):
        if p.is_file():dst.write(p,'assets/web/'+p.relative_to(HERE).as_posix(),compress_type=zipfile.ZIP_DEFLATED)
    for p in (deps/'aar/jni/arm64-v8a').glob('*.so'):
        dst.write(compat_bridge if p.name=='libUVCCamera.so' else p,'lib/arm64-v8a/'+p.name,compress_type=zipfile.ZIP_DEFLATED)
aligned=work/'aligned.apk';run([align,'-f','-p','4',base,aligned])
out=Path(os.environ.get('ZX_DASHBOARD_BUILD_OUT',str(ROOT/'output/onboard_dashboard')));out.mkdir(parents=True,exist_ok=True)
apk=out/'zhixing-dashboard.apk'
run([jdk/'java.exe','-jar',signer,'sign','--ks',CACHE/'zhixing-debug.keystore','--ks-pass','pass:android','--key-pass','pass:android','--out',apk,aligned])
run([jdk/'java.exe','-jar',signer,'verify','--verbose',apk])
report={'package':'cn.zhixing.dashboard','version':re.search(r'android:versionName="([^"]+)"',(HERE/'android/AndroidManifest.xml').read_text(encoding='utf8')).group(1),'apk':str(apk),'sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),'signature':'VERIFIED','build':'PASS','pc_backend_dependency':False,'physical_wifi':'NOT_YET_VERIFIED','physical_usb_in_new_package':'NOT_YET_VERIFIED','camera':'IMPLEMENTED_NOT_YET_VERIFIED','gimbal_control':'CAPABILITY_GATED_P7_MANUAL; physical acceptance pending','video_recording':'IMPLEMENTED_NOT_YET_VERIFIED','motor_commands':'CAPABILITY_GATED_MANUAL_FILMING; range advisory, ground steering acceptance pending'}
report['deployment']='BUILT_NOT_INSTALLED; installation and physical acceptance must be recorded separately'
report['version_code']=int(re.search(r'android:versionCode="([0-9]+)"',(HERE/'android/AndroidManifest.xml').read_text(encoding='utf8')).group(1))
report['camera_compatibility']={'bridge_sha256':hashlib.sha256(compat_bridge.read_bytes()).hexdigest(),'native_format_dispatch':'YUYV/UYVY to RGBX; original MJPEG path retained','system_enumeration':'NOT_FIXED_OR_VERIFIED_BY_APP_BUILD','borrowed_camera_phone_stream':'NOT_VERIFIED'}
report['previous_installed_network_acceptance']='network-acceptance.json if present; applies only to its recorded APK hash'
(out/'build-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
