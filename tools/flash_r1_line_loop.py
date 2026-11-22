"""Update the exact installed trial image, with full backup/readback and rollback."""
import json,hashlib
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_line_loop';flash.out=flash.root/'知行回路软件/build/r1_line_loop';flash.source=flash.out/'source-snapshot';flash.work=flash.tools/'line-loop-flash'
flash.BASELINE_PATH=flash.root/'output/onboard_dashboard/curve-follow-20261106/previous-mcu.bin'
assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()=='9aee184fc4b3778df2d14eab48fb59409bcc701f7d4dfc33e8644f168ae83f6b'
assert json.loads((flash.out/'build_result.json').read_text(encoding='utf-8'))['limits']['recovery_ms']==800
if __name__=='__main__':flash.main()
