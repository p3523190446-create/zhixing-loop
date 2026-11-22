"""Verify deployed motor firmware before PA0/PA1 gimbal upgrade, with full backup."""
import hashlib,json
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_gimbal_tim5';flash.out=flash.root/'知行回路软件/build'/flash.STEM
flash.source=flash.out/'source-snapshot';flash.work=flash.tools/'gimbal-tim5-flash'
base=flash.root/'知行回路软件/build/r1_motor_run_live_voltage'
proof=json.loads((base/'flash-verification.json').read_text(encoding='utf8'))
assert proof['flash']==proof['readback']=='PASS'
flash.BASELINE_PATH=base/'live-readback.bin'
assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()==proof['binary_sha256']
if __name__=='__main__':flash.main()
