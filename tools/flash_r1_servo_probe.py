"""Uses verified native backup/readback installer; hardware only with --execute."""
import sys,hashlib,json,shutil
import flash_r1_ultrasonic_probe as flash
flash.STEM='r1_servo_probe';flash.BASE_STEM='r1_ultrasonic_probe'
flash.out=flash.root/'知行回路软件/build'/flash.STEM
flash.source=flash.root/'知行回路软件/board'/flash.STEM
flash.work=flash.tools/'servo-native-flash'
if __name__=='__main__':
    if '--update-from-servo' in sys.argv:
        sys.argv.remove('--update-from-servo')
        proof=json.loads((flash.out/'flash-verification.json').read_text(encoding='utf-8'))
        assert proof['flash']=='PASS' and proof['readback']=='PASS'
        flash.BASELINE_PATH=flash.out/'live-readback.bin'
        assert hashlib.sha256(flash.BASELINE_PATH.read_bytes()).hexdigest()==proof['binary_sha256']
        shutil.copy2(flash.out/'flash-verification.json',flash.out/(proof['date']+'-flash-verification.json'))
    flash.main()
