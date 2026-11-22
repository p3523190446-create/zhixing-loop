"""Exact V2 baseline -> V3 empirical output profile, with full backup/readback."""
import hashlib
import json
import flash_r1_ultrasonic_probe as flash

flash.STEM = 'r1_mecanum_groundmap'
flash.out = flash.root / '知行回路软件/build' / flash.STEM
flash.source = flash.out / 'source-snapshot'
flash.work = flash.tools / 'mecanum-groundmap-flash'
flash.BASELINE_PATH = flash.root / '知行回路软件/build/r1_mecanum_integrated/r1_mecanum_integrated.bin'
assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest() == '0a2dd5c0a2d27ba8394a7d91b9e822cfd5a18722426b20213dab895536f23d84'
if __name__ == '__main__':
    assert json.loads((flash.out / 'controller-host-verification.json').read_text())['result'] == 'PASS'
    flash.main()
