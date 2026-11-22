"""Exact deployed IMU baseline guard, full backup, readback and rollback."""
import hashlib,json
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_line_task';flash.out=flash.root/'知行回路软件/build'/flash.STEM
flash.source=flash.out/'source-snapshot';flash.work=flash.tools/'line-task-flash'
flash.BASELINE_PATH=flash.root/'知行回路软件/build/r1_imu_observer/live-readback.bin'
assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()=='dae5b42946f86880e2a71a0f22520cca582fb1a3bb88700e1b04152951cd725f'
assert json.loads((flash.out/'build_result.json').read_text(encoding='utf-8'))['ground_permission'] is False
if __name__=='__main__':flash.main()
