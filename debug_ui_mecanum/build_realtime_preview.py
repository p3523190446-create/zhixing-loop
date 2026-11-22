"""Build a frozen real-time preview without overwriting the diagnostic APK/cache."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET
import argparse

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
sys.path.insert(0,str(ROOT/'知行回路软件/phone_vision'))
from build import CACHE,unique,run

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--variant',choices=['realtime','http-sync'],default='realtime')
args=parser.parse_args()
variant=args.variant
work=Path.home()/('.cache/zhixing-http-sync-preview-build' if variant=='http-sync' else '.cache/zhixing-realtime-preview-build')
out=ROOT/('output/onboard_dashboard/http-sync-preview' if variant=='http-sync' else 'output/low_latency/android-preview')
work.mkdir(parents=True,exist_ok=True)
out.mkdir(parents=True,exist_ok=True)
sources=out/'source-snapshot'
sources.mkdir(exist_ok=True)
inventory={}
for source in sorted((HERE/'android').glob('*')):
    if source.is_file():
        data=source.read_bytes();(sources/source.name).write_bytes(data)
        inventory['android/'+source.name]=hashlib.sha256(data).hexdigest()
for source in [HERE/'index.html',*sorted((HERE/'assets').rglob('*'))]:
    if source.is_file():
        relative=source.relative_to(HERE).as_posix();data=source.read_bytes()
        target=sources/'web'/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        inventory[relative]=hashlib.sha256(data).hexdigest()
classes=work/'classes'
if classes.exists():
    assert classes.resolve().is_relative_to(work.resolve())
    shutil.rmtree(classes)
classes.mkdir()
dex=work/'dex';dex.mkdir(exist_ok=True)
core=work/'uvc-core.jar'
deps=ROOT/'tmp/uvc-android'
with zipfile.ZipFile(deps/'aar/classes.jar') as src,zipfile.ZipFile(core,'w') as dst:
    for name in src.namelist():
        if (name.startswith('com/serenegiant/usb/') and not name.startswith('com/serenegiant/usb/CameraDialog')) or name.startswith('com/serenegiant/utils/HandlerThreadHandler') or name=='com/serenegiant/uvccamera/BuildConfig.class':dst.writestr(name,src.read(name))
android=unique('platform-33-ext3_r03/**/android.jar')
aapt=unique('build-tools_r35_windows/**/aapt2.exe');d8=unique('build-tools_r35_windows/**/lib/d8.jar')
signer=unique('build-tools_r35_windows/**/lib/apksigner.jar');align=unique('build-tools_r35_windows/**/zipalign.exe')
jdk=Path(os.environ['JAVA_HOME'])/'bin'
run([jdk/'javac.exe','-encoding','UTF-8','--release','8','-classpath',str(android)+os.pathsep+str(core),'-d',classes,*sorted(sources.glob('*.java'))])
jar=work/'classes.jar'
with zipfile.ZipFile(jar,'w') as dst:
    for p in classes.rglob('*.class'):dst.write(p,p.relative_to(classes).as_posix())
run([jdk/'java.exe','-cp',d8,'com.android.tools.r8.D8','--min-api','26','--lib',android,'--output',dex,jar,core])
base=work/'base.apk';run([aapt,'link','-I',android,'--manifest',sources/'AndroidManifest.xml','-o',base])
with zipfile.ZipFile(base,'a') as dst:
    dst.write(dex/'classes.dex','classes.dex',compress_type=zipfile.ZIP_DEFLATED)
    for p in (sources/'web').rglob('*'):
        if p.is_file():dst.write(p,'assets/web/'+p.relative_to(sources/'web').as_posix(),compress_type=zipfile.ZIP_DEFLATED)
    for p in (deps/'aar/jni/arm64-v8a').glob('*.so'):dst.write(p,'lib/arm64-v8a/'+p.name,compress_type=zipfile.ZIP_DEFLATED)
aligned=work/'aligned.apk';run([align,'-f','-p','4',base,aligned])
apk=out/('zhixing-dashboard-http-sync-preview.apk' if variant=='http-sync' else 'zhixing-dashboard-realtime-preview.apk')
run([jdk/'java.exe','-jar',signer,'sign','--ks',CACHE/'zhixing-debug.keystore','--ks-pass','pass:android','--key-pass','pass:android','--out',apk,aligned])
run([jdk/'java.exe','-jar',signer,'verify','--verbose',apk])
manifest=ET.parse(sources/'AndroidManifest.xml').getroot()
report={'variant':'HTTP_SYNC_FIX' if variant=='http-sync' else 'REALTIME_PREVIEW','package':'cn.zhixing.dashboard',
        'version':manifest.get('{http://schemas.android.com/apk/res/android}versionName'),
        'apk':str(apk),'sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),
        'build':'PASS','signature':'VERIFIED','deployment':'NOT_INSTALLED_BY_THIS_TASK',
        'source_sha256':inventory,'status_push_hz':10,'sensor_sampling_hz':1,
        'target_send_period_ms':200,'network_transport':'HTTP by default; reserved WebSocket requires explicit transport=ws',
        'physical_hotspot_latency':'NOT_MEASURED','physical_mcu_write_latency':'NOT_MEASURED',
        'gimbal_control':'CAPABILITY_GATED_BY_CURRENT_TELEMETRY_SERVICE; not physically tested by this builder','mcu_changed':False,
        'main_diagnostic_apk':'NOT_OVERWRITTEN_BY_THIS_BUILDER'}
(out/'build-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},ensure_ascii=False))
