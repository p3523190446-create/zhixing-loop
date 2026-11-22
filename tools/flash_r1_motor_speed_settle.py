import flash_r1_motor_probe as flash
flash.OUT=flash.PROJECT/'知行回路软件/build/r1_motor_speed_settle'
flash.WORK=flash.TOOLS/'r1-motor-speed-settle'
flash.ELF=flash.WORK/'r1_motor_speed_settle.elf'
flash.BASE=flash.TOOLS/'r1-motor-speed/r1_motor_speed.elf'
if __name__=='__main__':flash.main()
