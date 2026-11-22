import flash_r1_motor_probe as flash
flash.OUT=flash.PROJECT/'知行回路软件/build/r1_motor_filtered'
flash.WORK=flash.TOOLS/'r1-motor-filtered'
flash.ELF=flash.WORK/'r1_motor_filtered.elf'
flash.BASE=flash.TOOLS/'r1-motor-smooth/r1_motor_smooth.elf'
if __name__=='__main__':flash.main()
