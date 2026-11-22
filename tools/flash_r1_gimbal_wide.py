import json,hashlib
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_gimbal_wide';flash.BASE_STEM='r1_gimbal_manual'
flash.out=flash.root/'知行回路软件/build'/flash.STEM
flash.source=flash.root/'知行回路软件/board'/flash.STEM
flash.work=flash.tools/'gimbal-wide-native-flash'
if __name__=='__main__':
    live=json.loads((flash.root/'知行回路软件/remote_panel/telemetry.json').read_text(encoding='utf-8'))
    assert not live['control']['active'] and live['gimbal']['active']==0
    assert live['gimbal']['yaw_us']==live['gimbal']['pitch_us']==0
    old=flash.root/'知行回路软件/build/r1_gimbal_manual'
    proof=json.loads((old/'flash-verification.json').read_text(encoding='utf-8'))
    flash.BASELINE_PATH=old/'live-readback.bin'
    assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()==proof['binary_sha256']
    flash.main()
