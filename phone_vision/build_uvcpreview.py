from pathlib import Path
import os,zipfile,hashlib,json
from build import CACHE,unique,run,WORKSPACE
here=Path(__file__).resolve().parent/'uvcpreview'
work=Path.home()/'.cache/zhixing-uvcpreview-build';work.mkdir(exist_ok=True)
classes=work/'classes';classes.mkdir(exist_ok=True)
dex=work/'dex';dex.mkdir(exist_ok=True)
deps=WORKSPACE/'tmp/uvc-android'
library=deps/'aar/classes.jar'
core=work/'uvc-core.jar'
# Package only the library's USB/UVC path and its actual helper dependencies.
# CameraDialog and optional recording/UI classes are unused and not loaded.
with zipfile.ZipFile(library) as src,zipfile.ZipFile(core,'w') as dst:
 for n in src.namelist():
  if (n.startswith('com/serenegiant/usb/') and not n.startswith('com/serenegiant/usb/CameraDialog')) or n.startswith('com/serenegiant/utils/HandlerThreadHandler') or n=='com/serenegiant/uvccamera/BuildConfig.class':dst.writestr(n,src.read(n))
android=unique('platform-33-ext3_r03/**/android.jar');aapt=unique('build-tools_r35_windows/**/aapt2.exe');d8=unique('build-tools_r35_windows/**/lib/d8.jar');signer=unique('build-tools_r35_windows/**/lib/apksigner.jar');align=unique('build-tools_r35_windows/**/zipalign.exe');jdk=Path(os.environ['JAVA_HOME'])/'bin'
run([jdk/'javac.exe','-encoding','UTF-8','-source','8','-target','8','-bootclasspath',android,'-classpath',core,'-d',classes,here/'MainActivity.java'])
jar=work/'classes.jar'
with zipfile.ZipFile(jar,'w') as z:
 for p in classes.rglob('*.class'):z.write(p,p.relative_to(classes).as_posix())
run([jdk/'java.exe','-cp',d8,'com.android.tools.r8.D8','--min-api','24','--lib',android,'--output',dex,jar,core])
base=work/'base.apk';run([aapt,'link','-I',android,'--manifest',here/'AndroidManifest.xml','-o',base])
with zipfile.ZipFile(base,'a') as z:
 z.write(dex/'classes.dex','classes.dex',compress_type=zipfile.ZIP_DEFLATED)
 for p in (deps/'aar/jni/arm64-v8a').glob('*.so'):z.write(p,'lib/arm64-v8a/'+p.name,compress_type=zipfile.ZIP_DEFLATED)
 z.write(deps/'UVCAndroid-1.0.13.pom','assets/UVCAndroid-1.0.13.pom')
aligned=work/'aligned.apk';run([align,'-f','-p','4',base,aligned]);out=WORKSPACE/'output/usb_camera_check';out.mkdir(exist_ok=True);apk=out/'zhixing-uvcpreview.apk'
run([jdk/'java.exe','-jar',signer,'sign','--ks',CACHE/'zhixing-debug.keystore','--ks-pass','pass:android','--key-pass','pass:android','--out',apk,aligned]);run([jdk/'java.exe','-jar',signer,'verify','--verbose',apk])
result={'apk':str(apk),'package':'cn.zhixing.uvcpreview','sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),'build':'PASS','signature':'VERIFIED','camera_device':'145F:02EC only','camera_frames':'AWAITING_PHYSICAL_TEST','motor_control':'NONE','upstream':'com.herohan:UVCAndroid:1.0.13','upstream_aar_sha256':hashlib.sha256((deps/'UVCAndroid-1.0.13.aar').read_bytes()).hexdigest()}
(out/'preview-build-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
