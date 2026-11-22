import json
import build_r1_phone_standalone as prepared
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_phone_standalone';flash.out=prepared.build.OUT
flash.source=flash.out/'source-snapshot';flash.work=flash.tools/'phone-standalone-flash';flash.BASELINE_PATH=prepared.BASE_BINARY
if __name__=='__main__':
 assert json.loads((flash.out/'boot-policy-checks.json').read_text())['result']=='PASS'
 flash.main()
