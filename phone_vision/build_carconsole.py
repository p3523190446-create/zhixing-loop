"""Build foreground read-only car console without Gradle; no firmware changes."""
from pathlib import Path
import os,zipfile,hashlib,json,shutil
from build import CACHE,unique,run,WORKSPACE
here=Path(__file__).resolve().parent/'carconsole'
work=Path.home()/'.cache/zhixing-carconsole-build';work.mkdir(exist_ok=True)
classes=work/'classes';classes.mkdir(exist_ok=True);dex=work/'dex';dex.mkdir(exist_ok=True)
android=unique('platform-33-ext3_r03/**/android.jar');aapt=unique('build-tools_r35_windows/**/aapt2.exe')
d8=unique('build-tools_r35_windows/**/lib/d8.jar');signer=unique('build-tools_r35_windows/**/lib/apksigner.jar');align=unique('build-tools_r35_windows/**/zipalign.exe')
jdk=Path(os.environ['JAVA_HOME'])/'bin'
run([jdk/'javac.exe','-encoding','UTF-8','-source','8','-target','8','-bootclasspath',android,'-d',classes,*here.glob('*.java')])
jar=work/'classes.jar'
with zipfile.ZipFile(jar,'w') as z:
    for p in classes.rglob('*.class'):z.write(p,p.relative_to(classes).as_posix())
run([jdk/'java.exe','-cp',d8,'com.android.tools.r8.D8','--min-api','26','--lib',android,'--output',dex,jar])
shutil.copytree(here/'assets',work/'assets',dirs_exist_ok=True)
base=work/'base.apk';run([aapt,'link','-I',android,'--manifest',here/'AndroidManifest.xml','-A',work/'assets','-o',base])
with zipfile.ZipFile(base,'a') as z:z.write(dex/'classes.dex','classes.dex',compress_type=zipfile.ZIP_DEFLATED)
aligned=work/'aligned.apk';run([align,'-f','-p','4',base,aligned])
out=WORKSPACE/'output/car_phone';out.mkdir(parents=True,exist_ok=True);apk=out/'zhixing-carconsole.apk'
if apk.exists():
    archive=out/'releases';archive.mkdir(exist_ok=True)
    shutil.copy2(apk,archive/(hashlib.sha256(apk.read_bytes()).hexdigest()+'.apk'))
run([jdk/'java.exe','-jar',signer,'sign','--ks',CACHE/'zhixing-debug.keystore','--ks-pass','pass:android','--key-pass','pass:android','--out',apk,aligned])
run([jdk/'java.exe','-jar',signer,'verify','--verbose',apk])
r=dict(package='cn.zhixing.carconsole',version='0.3',apk=str(apk),sha256=hashlib.sha256(apk.read_bytes()).hexdigest(),build='PASS',signed=True,
    firmware_changed=False,motion_commands='NONE',physical_communication='NOT_YET_TESTED',background_recording='NOT_YET_TESTED')
(out/'build-result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(r,ensure_ascii=False))
