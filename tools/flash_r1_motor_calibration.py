import flash_r1_motor_probe as flash
flash.OUT=flash.PROJECT/'知行回路软件/build/r1_motor_calibration'
flash.WORK=flash.TOOLS/'r1-motor-calibration'
flash.ELF=flash.WORK/'r1_motor_calibration.elf'
flash.BASE=flash.TOOLS/'r1-motor-speed-settle/r1_motor_speed_settle.elf'
if __name__=='__main__':flash.main()
