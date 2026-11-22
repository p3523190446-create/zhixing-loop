"""Exact line-compat baseline guard, 256KiB backup, byte readback and rollback."""
import hashlib,sys
import flash_r1_ultrasonic_probe as flash
diag='--diag' in sys.argv
flash.STEM='r1_mpu6050_diag' if diag else 'r1_mpu6050';flash.out=flash.root/'知行回路软件/build'/flash.STEM
flash.source=flash.out/'source-snapshot';flash.work=flash.tools/'mpu6050-flash'
flash.BASELINE_PATH=flash.root/('知行回路软件/build/r1_mpu6050/live-readback.bin' if diag else '知行回路软件/build/r1_line_tracking_compat/live-readback.bin')
assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()==('d832b061f5aacd1134d0ab0c0f41b50fab1c5c47d496ba7f8e1cf66500261787' if diag else 'b4e8ebba9e7569b523d1283b66c08681df6ca390b7fe9c694f39399f167baeb9')
if __name__=='__main__':flash.main()
