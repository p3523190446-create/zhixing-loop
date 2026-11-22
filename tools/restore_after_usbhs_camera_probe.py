"""Restore verified normal firmware after the isolated host descriptor test."""
import json,hashlib
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_gimbal_usbfs_remote';flash.BASE_STEM='r1_usbhs_camera_probe'
flash.out=flash.root/'知行回路软件/build'/flash.STEM
flash.source=flash.root/'知行回路软件/board'/flash.STEM
flash.work=flash.tools/'restore-usbhs-camera-probe'
if __name__=='__main__':
    probe=flash.root/'知行回路软件/build/r1_usbhs_camera_probe'
    proof=json.loads((probe/'flash-verification.json').read_text(encoding='utf8'))
    assert proof['flash']=='PASS' and proof['readback']=='PASS'
    flash.BASELINE_PATH=probe/'live-readback.bin'
    assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()==proof['binary_sha256']
    flash.main()
