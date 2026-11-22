"""Apply the previously tested mecanum deltas to the CURRENT dashboard in place."""
from pathlib import Path
import hashlib,json,shutil,textwrap
from prepare_mecanum import replace
import prepare_mecanum_controls as controls
import prepare_mecanum_pc as pc
SW=Path(__file__).resolve().parents[1];UI=SW/'debug_ui'
OUT=SW.parent/'output/onboard_dashboard/mecanum-live-20261107'
NAMES=['android/DriveBroker.java','android/TelemetryService.java','android/GatewayService.java','android/BoardReplyException.java','android/AndroidManifest.xml','assets/features/drive.js','index.html','speed_server.py','pc_integration.py']

def main():
 OUT.mkdir(parents=True,exist_ok=True);before=OUT/'before-current-ui'
 assert not before.exists(),'Deltas already staged; inspect before applying again'
 original={n:(UI/n).read_bytes() for n in NAMES}
 for n,data in original.items():
  p=before/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 try:
  # Reuse the original reviewed transformation, while retaining newer modules.
  source=(SW/'tools/prepare_mecanum.py').read_text(encoding='utf-8')
  start="    p=UI/'android/BoardReplyException.java';"
  chunk=start+source.split(start,1)[1].split('    manifest=',1)[0]
  chunk=chunk.replace('private volatile boolean lineCapable;', 'private volatile boolean lineCapable,mpuCapable,imuFeaturesCapable;')
  chunk=chunk.replace('private volatile boolean lineCapable,driveMecanum;', 'private volatile boolean lineCapable,mpuCapable,imuFeaturesCapable,driveMecanum;')
  chunk=chunk.replace('R1_DRIVE_STARTUP_MANUAL_MECANUM_V1_20261026','R1_DRIVE_STARTUP_MANUAL_MECANUM_V2_20261107')
  exec(textwrap.dedent(chunk),{'UI':UI,'replace':replace})
  controls.UI=UI;controls.main()
  pc.UI=UI;pc.main()
  p=UI/'speed_server.py';s=p.read_text(encoding='utf-8').replace('R1_DRIVE_STARTUP_MANUAL_MECANUM_V1_20261026','R1_DRIVE_STARTUP_MANUAL_MECANUM_V2_20261107').replace("manual_stem='r1_mecanum'", "manual_stem='r1_mecanum_integrated'");p.write_text(s,encoding='utf-8')
  p=UI/'android/AndroidManifest.xml';s=p.read_text(encoding='utf-8');s=replace(s,'android:versionCode="25"','android:versionCode="27"');s=replace(s,'android:versionName="0.25.8"','android:versionName="0.26.1"');p.write_text(s,encoding='utf-8')
  report={n:{'before':hashlib.sha256(original[n]).hexdigest(),'after':hashlib.sha256((UI/n).read_bytes()).hexdigest()} for n in NAMES}
  (OUT/'source-deltas.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 except Exception:
  for n,data in original.items():(UI/n).write_bytes(data)
  raise
 print('CURRENT UI deltas applied; originals backed up; no device access')

if __name__=='__main__':main()
