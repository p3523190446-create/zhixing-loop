"""Prepared flasher entry. Do not execute until user resumes device work."""
import sys


if __name__ == '__main__':
    if '--execute' not in sys.argv[1:]:
        print('Prepared only. No programmer or serial port accessed.')
        sys.exit(0)
    sys.argv.remove('--execute')
    import flash_r1_motor_probe as flash
    flash.OUT=flash.PROJECT/'知行回路软件/build/r1_motor_stable'
    flash.WORK=flash.TOOLS/'r1-motor-stable'
    flash.ELF=flash.WORK/'r1_motor_stable.elf'
    flash.BASE=flash.TOOLS/'r1-motor-calibrated/r1_motor_calibrated.elf'
    flash.main()
