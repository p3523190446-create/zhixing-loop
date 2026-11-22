"""Update the exact installed trial image, with full backup/readback and rollback."""
import json,hashlib
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_line_continuous';flash.out=flash.root/'知行回路软件/build/r1_line_continuous';flash.source=flash.out/'source-snapshot';flash.work=flash.tools/'line-continuous-flash'
flash.BASELINE_PATH=flash.root/'output/onboard_dashboard/curve-follow-fix2-20261106/previous-mcu.bin'
assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()=='99a04f62c96abf4eafeb8aec718e4e45e8dc4b3632e1b735477d8f778355f815'
assert json.loads((flash.out/'build_result.json').read_text(encoding='utf-8'))['limits']['recovery_ms']==0
if __name__=='__main__':flash.main()
