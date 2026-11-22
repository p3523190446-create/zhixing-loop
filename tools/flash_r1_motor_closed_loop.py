import flash_r1_motor_probe as flash
flash.OUT=flash.PROJECT/'知行回路软件/build/r1_motor_closed_loop'
flash.WORK=flash.TOOLS/'r1-motor-closed-loop'
flash.ELF=flash.WORK/'r1_motor_closed_loop.elf'
flash.BASE=flash.TOOLS/'r1-motor-calibration/r1_motor_calibration.elf'
if __name__=='__main__':flash.main()
