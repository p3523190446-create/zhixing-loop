"""Use the existing verified updater; preserve all four phone preference files."""
from pathlib import Path
import hashlib,json,subprocess,sys,argparse
ROOT=Path(__file__).resolve().parents[2];UI=ROOT/'知行回路软件/debug_ui'
OUT=ROOT/'output/onboard_dashboard/gimbal-follow-20261107'
ADB=ROOT/'tmp/android-tools/platform-tools/adb.exe'
def adb(*args):return subprocess.run([str(ADB),*args],check=True,capture_output=True,timeout=30).stdout
def preferences():
 return {n:hashlib.sha256(adb('shell','run-as','cn.zhixing.dashboard','cat','shared_prefs/'+n+'.xml')).hexdigest()
         for n in ['web','gimbal_profile','line_calibration','large_vision']}
def main():
 global OUT
 parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=OUT);OUT=parser.parse_args().out
 before=preferences()
 (OUT/'settings-before.json').write_text(json.dumps(before),encoding='utf-8')
 subprocess.run([sys.executable,str(UI/'install_camera_compat.py'),'--out',str(OUT)],check=True)
 after=preferences()
 if before!=after:raise RuntimeError('Preference change detected; inspect before continuing')
 report={'preserved':True,'before':before,'after':after,'firmware_changed':False,'actuator_commands_sent':False}
 (OUT/'settings-preserved.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 adb('shell','am','start','-n','cn.zhixing.dashboard/.MainActivity')
 print(json.dumps({'installed':True,'settings_preserved':list(before),'version':json.loads((OUT/'build-result.json').read_text(encoding='utf-8'))['version'],'physical_tracking_tested':False}))
if __name__=='__main__':main()
