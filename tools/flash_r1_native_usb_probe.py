"""Opt-in --execute after disconnected motors/servos, normal J2 and P9 PC ready.
256KiB live backup, known baseline check, readback and automatic rollback.
"""
import json,hashlib
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_native_usb_probe';flash.BASE_STEM='r1_gimbal_wide'
flash.out=flash.root/'知行回路软件/build'/flash.STEM
flash.source=flash.root/'知行回路软件/board'/flash.STEM
flash.work=flash.tools/'native-usb-probe-flash'
if __name__=='__main__':
    proof=json.loads((flash.root/'知行回路软件/build/r1_gimbal_wide/flash-verification.json').read_text(encoding='utf-8'))
    flash.BASELINE_PATH=flash.root/'知行回路软件/build/r1_gimbal_wide/live-readback.bin'
    assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()==proof['binary_sha256']
    flash.main()
