import hashlib,json
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_drive_startup_stable_v2';flash.out=flash.root/'知行回路软件/build'/flash.STEM
flash.source=flash.out/'source-snapshot';flash.work=flash.tools/'drive-startup-stable-v2-flash'
base=flash.root/'知行回路软件/build/r1_drive_startup_stable';proof=json.loads((base/'flash-verification.json').read_text(encoding='utf8'))
assert proof['flash']==proof['readback']=='PASS'
flash.BASELINE_PATH=base/'live-readback.bin';assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()==proof['binary_sha256']
if __name__=='__main__':flash.main()
