"""Native backup/readback installer from verified fixed-pattern gimbal variant."""
import json,hashlib
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_gimbal_continuous';flash.BASE_STEM='r1_gimbal_probe'
flash.out=flash.root/'知行回路软件/build'/flash.STEM
flash.source=flash.root/'知行回路软件/board'/flash.STEM
flash.work=flash.tools/'gimbal-continuous-native-flash'
if __name__=='__main__':
    old=flash.root/'知行回路软件/build/r1_gimbal_probe'
    proof=json.loads((old/'flash-verification.json').read_text(encoding='utf-8'))
    assert proof['flash']=='PASS' and proof['readback']=='PASS'
    flash.BASELINE_PATH=old/'live-readback.bin'
    assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()==proof['binary_sha256']
    flash.main()
