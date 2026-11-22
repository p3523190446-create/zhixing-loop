"""User-ready P9 install: full backup, exact installed baseline, readback, rollback.
Phone/P7, motor battery and servo power must be disconnected first.
"""
import hashlib,json
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_usbfs_dma_recovery'
flash.out=flash.root/'知行回路软件/build'/flash.STEM
flash.source=flash.root/'知行回路软件/board'/flash.STEM
flash.work=flash.tools/'usbfs-dma-recovery-flash'
base=flash.root/'知行回路软件/build/r1_usbhs_camera_bridge_usb_lifecycle'
proof=json.loads((base/'flash-verification.json').read_text(encoding='utf8'))
assert proof['flash']==proof['readback']=='PASS'
flash.BASELINE_PATH=base/'live-readback.bin'
assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()==proof['binary_sha256']
if __name__=='__main__':flash.main()
