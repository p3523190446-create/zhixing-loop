"""Backup, exact MPU baseline guard, byte readback, rollback on failure."""
import hashlib
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_imu_observer';flash.out=flash.root/'知行回路软件/build'/flash.STEM
flash.source=flash.out/'source-snapshot';flash.work=flash.tools/'imu-observer-flash'
flash.BASELINE_PATH=flash.root/'知行回路软件/build/r1_mpu6050_diag/live-readback.bin'
assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()=='ce000d746c5dee64181336a0b297ab13eeb21757237069e1bfa8365266e9b7e0'
if __name__=='__main__':flash.main()
