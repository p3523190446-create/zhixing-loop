import flash_r1_motor_probe as flash
flash.OUT=flash.PROJECT/'知行回路软件/build/r1_motor_config'
flash.WORK=flash.TOOLS/'r1-motor-config'
flash.ELF=flash.WORK/'r1_motor_config.elf'
flash.BASE=flash.TOOLS/'r1-motor-parameters/r1_motor_parameters.elf'
if __name__=='__main__':flash.main()
