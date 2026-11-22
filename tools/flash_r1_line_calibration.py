"""Update the exact deployed line-task image; backup/readback/rollback, gate stays closed."""
import hashlib,json
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_line_task';flash.out=flash.root/'知行回路软件/build/r1_line_task'
flash.source=flash.out/'source-snapshot';flash.work=flash.tools/'line-calibration-flash'
flash.BASELINE_PATH=flash.root/'output/onboard_dashboard/phone-line-calibration-20261027/previous-mcu.bin'
assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()=='ca0e9ac17ff5411dc10fe7d7a146b75c87bdedaa74bc3efa87e47b305f0e3853'
assert json.loads((flash.out/'build_result.json').read_text(encoding='utf-8'))['ground_permission'] is False
if __name__=='__main__':flash.main()
