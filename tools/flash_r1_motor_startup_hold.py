"""Prepared flasher entry. Do not execute until user resumes device work."""
import sys


if __name__ == '__main__':
    if '--execute' not in sys.argv[1:]:
        print('Prepared only. No programmer or serial port accessed.')
        sys.exit(0)
    sys.argv.remove('--execute')
    import flash_r1_motor_probe as flash
    flash.OUT=flash.PROJECT/'知行回路软件/build/r1_motor_startup_hold'
    flash.WORK=flash.TOOLS/'r1-motor-startup-hold'
    flash.ELF=flash.WORK/'r1_motor_startup_hold.elf'
    flash.BASE=flash.TOOLS/'r1-motor-low-start/r1_motor_low_start.elf'
    flash.main()
