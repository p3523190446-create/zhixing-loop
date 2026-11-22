"""Exact baseline, full backup/readback/rollback; user operates the first trial."""
import json,hashlib
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_line_trial';flash.out=flash.root/'知行回路软件/build/r1_line_trial';flash.source=flash.out/'source-snapshot';flash.work=flash.tools/'line-trial-flash'
flash.BASELINE_PATH=flash.root/'output/onboard_dashboard/line-start-fix-20261106/previous-mcu.bin'
assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()=='be47172b300dcf5900635aba877b1c893aa68d253e2349606b237a334288d22f'
assert json.loads((flash.out/'build_result.json').read_text(encoding='utf-8'))['limits']==dict(speed=40,max_ms=5000,branch=0)
if __name__=='__main__':flash.main()
