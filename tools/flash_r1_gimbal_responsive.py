"""Use the existing full-backup, exact-baseline and rollback flasher."""
import json
import build_r1_gimbal_responsive as prepared
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_gimbal_responsive';flash.out=prepared.build.OUT
flash.source=flash.out/'source-snapshot';flash.work=flash.tools/'gimbal-responsive-flash'
flash.BASELINE_PATH=prepared.BASE_BINARY
if __name__=='__main__':
 assert json.loads((flash.out/'responsive-checks.json').read_text())['result']=='PASS'
 flash.main()
