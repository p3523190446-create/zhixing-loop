"""Use only with motor battery disconnected and confirmed PC10/PC11 sensor wiring.
Back up the current 256KiB image; require exact v8 baseline; verify new bytes.
"""
import hashlib
import json
import flash_r1_ultrasonic_probe as flash

flash.STEM='r1_line_tracking'
flash.out=flash.root/'知行回路软件/build'/flash.STEM
flash.source=flash.out/'source-snapshot'
flash.work=flash.tools/'line-tracking-static-flash'
base=flash.root/'知行回路软件/build/r1_official_tt_v8'
meta=json.loads((base/'build_result.json').read_text(encoding='utf-8'))
flash.BASELINE_PATH=base/'r1_official_tt_v8.bin'
assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()==meta['binary_sha256']
assert meta['binary_sha256']=='5f2abf2c1869168982e7faba37677ad595f5af12159ce7bdda04b3398167c3e4'
if __name__=='__main__':flash.main()
