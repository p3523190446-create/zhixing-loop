"""Package the already-built algorithm-only benchmark as a standalone phone app."""
import bootstrap
from pathlib import Path
import hashlib,importlib.util,json,os,zipfile

HERE=Path(__file__).resolve().parent
OUT=bootstrap.ROOT/'output/onboard_dashboard/phone-first-20261025'
WORK=Path.home()/'.cache/zhixing-phone-bench-apk-20261025'

def main():
    WORK.mkdir(parents=True,exist_ok=True)
    spec=importlib.util.spec_from_file_location('existing_tools',HERE.parent/'phone_vision/build.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    android=helper.unique('platform-33-ext3_r03/**/android.jar')
    aapt=helper.unique('build-tools_r35_windows/**/aapt2.exe');d8=helper.unique('build-tools_r35_windows/**/lib/d8.jar')
    signer=helper.unique('build-tools_r35_windows/**/lib/apksigner.jar');align=helper.unique('build-tools_r35_windows/**/zipalign.exe')
    jdk=Path(os.environ['JAVA_HOME'])/'bin';classes=WORK/'classes';classes.mkdir(exist_ok=True)
    helper.run([jdk/'javac.exe','-encoding','UTF-8','--release','8','-classpath',android,'-d',classes,HERE/'phone_local_bench/MainActivity.java'])
    jar=WORK/'classes.jar'
    with zipfile.ZipFile(jar,'w') as archive:
        for path in classes.rglob('*.class'):archive.write(path,path.relative_to(classes).as_posix())
    dex=WORK/'dex';dex.mkdir(exist_ok=True)
    helper.run([jdk/'java.exe','-cp',d8,'com.android.tools.r8.D8','--min-api','24','--lib',android,'--output',dex,jar])
    base=WORK/'base.apk';helper.run([aapt,'link','-I',android,'--manifest',HERE/'phone_local_bench/AndroidManifest.xml','-o',base])
    with zipfile.ZipFile(base,'a') as archive:
        archive.write(dex/'classes.dex','classes.dex')
        for name in ['zx_local_bench','yolov8n.ncnn.param','yolov8n.ncnn.bin','frame.rgb']:archive.write(OUT/name,'assets/'+name)
    aligned=WORK/'aligned.apk';helper.run([align,'-f','-p','4',base,aligned])
    apk=OUT/'zhixing-phone-local-bench-0.1.apk'
    helper.run([jdk/'java.exe','-jar',signer,'sign','--ks',helper.CACHE/'zhixing-debug.keystore','--ks-pass','pass:android','--key-pass','pass:android','--out',apk,aligned])
    helper.run([jdk/'java.exe','-jar',signer,'verify','--verbose',apk])
    report=dict(apk=str(apk),package='cn.zhixing.localbench',sha256=hashlib.sha256(apk.read_bytes()).hexdigest(),
        permissions=[],scope='Offline algorithm benchmark, not live camera/car application',build='PASS')
    (OUT/'apk-build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))

if __name__=='__main__':main()
