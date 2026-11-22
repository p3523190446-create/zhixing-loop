"""Back up/readback verified line v1 before installing identity-only compatibility fix."""
import hashlib
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_line_tracking_compat';flash.out=flash.root/'知行回路软件/build'/flash.STEM
flash.source=flash.out/'source-snapshot';flash.work=flash.tools/'line-tracking-compat-flash'
flash.BASELINE_PATH=flash.root/'知行回路软件/build/r1_line_tracking/live-readback.bin'
assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()=='c572ee833dc780c5b66b6b8319ef89902ccf76ec3e285cc748a872f859650a75'
if __name__=='__main__':flash.main()
