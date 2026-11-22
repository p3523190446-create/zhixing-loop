"""Build restricted, dependency-free Android USB CDC read-only probe."""
from pathlib import Path
import os,zipfile,hashlib,json
from build import CACHE,unique,run,WORKSPACE
here=Path(__file__).resolve().parent/'boardlinkprobe'
work=Path.home()/'.cache/zhixing-boardlinkprobe-build';work.mkdir(exist_ok=True)
classes=work/'classes';classes.mkdir(exist_ok=True)
dex=work/'dex';dex.mkdir(exist_ok=True)
android=unique('platform-33-ext3_r03/**/android.jar')
aapt=unique('build-tools_r35_windows/**/aapt2.exe')
d8=unique('build-tools_r35_windows/**/lib/d8.jar')
signer=unique('build-tools_r35_windows/**/lib/apksigner.jar')
align=unique('build-tools_r35_windows/**/zipalign.exe')
jdk=Path(os.environ['JAVA_HOME'])/'bin'
run([jdk/'javac.exe','-encoding','UTF-8','-source','8','-target','8','-bootclasspath',android,'-d',classes,here/'MainActivity.java'])
jar=work/'classes.jar'
with zipfile.ZipFile(jar,'w') as z:
    for p in classes.rglob('*.class'):z.write(p,p.relative_to(classes).as_posix())
run([jdk/'java.exe','-cp',d8,'com.android.tools.r8.D8','--min-api','24','--lib',android,'--output',dex,jar])
base=work/'base.apk';run([aapt,'link','-I',android,'--manifest',here/'AndroidManifest.xml','-o',base])
with zipfile.ZipFile(base,'a') as z:z.write(dex/'classes.dex','classes.dex',compress_type=zipfile.ZIP_DEFLATED)
aligned=work/'aligned.apk';run([align,'-f','-p','4',base,aligned])
out=WORKSPACE/'output/phone_board_link';out.mkdir(exist_ok=True)
apk=out/'zhixing-boardlinkprobe.apk'
run([jdk/'java.exe','-jar',signer,'sign','--ks',CACHE/'zhixing-debug.keystore','--ks-pass','pass:android','--key-pass','pass:android','--out',apk,aligned])
run([jdk/'java.exe','-jar',signer,'verify','--verbose',apk])
result={'apk':str(apk),'package':'cn.zhixing.boardlinkprobe','version':'0.10','sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),'build':'PASS','signature':'VERIFIED','queries':['PING','STATUS','GIMBAL_STATUS','ULTRA_STATUS'],'loopback_tokens':['ZX_LOOP_A01','ZX_LOOP_B02','ZX_LOOP_C03'],'native_queries':['PING','NATIVE_ID','ZX_NATIVE_A01','ZX_NATIVE_B02','ZX_NATIVE_C03'],'motor_control':'NONE','firmware_changes':'NONE','physical_usb_communication':'NOT_YET_TESTED'}
(out/'build-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
