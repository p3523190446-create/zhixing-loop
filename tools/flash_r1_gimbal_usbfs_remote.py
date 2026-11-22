"""Full backup/readback/rollback; opt-in only after P9 readiness confirmed."""
import json,hashlib
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_gimbal_usbfs_remote';flash.BASE_STEM='r1_gimbal_usbfs'
flash.out=flash.root/'知行回路软件/build'/flash.STEM
flash.source=flash.root/'知行回路软件/board'/flash.STEM
flash.work=flash.tools/'gimbal-usbfs-remote-flash'
if __name__=='__main__':
    base=flash.root/'知行回路软件/build/r1_gimbal_usbfs'
    proof=json.loads((base/'flash-verification.json').read_text(encoding='utf-8'))
    flash.BASELINE_PATH=base/'live-readback.bin'
    assert proof['flash']=='PASS' and proof['readback']=='PASS'
    assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()==proof['binary_sha256']
    flash.main()
