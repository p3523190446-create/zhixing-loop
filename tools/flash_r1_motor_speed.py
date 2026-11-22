import flash_r1_motor_probe as flash
flash.OUT=flash.PROJECT/'知行回路软件/build/r1_motor_speed'
flash.WORK=flash.TOOLS/'r1-motor-speed'
flash.ELF=flash.WORK/'r1_motor_speed.elf'
flash.BASE=flash.TOOLS/'r1-motor-config/r1_motor_config.elf'
if __name__=='__main__':flash.main()
