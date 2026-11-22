"""Reuse verified backup/readback/rollback flasher for this exact deployed base."""
import json,hashlib
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_mecanum_integrated'
flash.out=flash.root/'知行回路软件/build'/flash.STEM
flash.source=flash.out/'source-snapshot'
flash.work=flash.tools/'mecanum-integrated-flash'
flash.BASELINE_PATH=flash.root/'知行回路软件/build/r1_line_continuous/r1_line_continuous.bin'
assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()=='512304f64cc446125c09d0fae36fa90d04aea0f56616d8c612e492f8fe34aad0'
assert json.loads((flash.out/'controller-host-verification.json').read_text())['result']=='PASS'
if __name__=='__main__':flash.main()
