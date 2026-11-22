import flash_r1_motor_probe as flash
flash.OUT=flash.PROJECT/'知行回路软件/build/r1_motor_smooth'
flash.WORK=flash.TOOLS/'r1-motor-smooth'
flash.ELF=flash.WORK/'r1_motor_smooth.elf'
flash.BASE=flash.TOOLS/'r1-motor-tuning/r1_motor_tuning.elf'
if __name__=='__main__':flash.main()
