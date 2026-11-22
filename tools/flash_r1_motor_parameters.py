import flash_r1_motor_probe as flash
flash.OUT=flash.PROJECT/'知行回路软件/build/r1_motor_parameters'
flash.WORK=flash.TOOLS/'r1-motor-parameters'
flash.ELF=flash.WORK/'r1_motor_parameters.elf'
flash.BASE=flash.TOOLS/'r1-motor-encoder/r1_motor_encoder.elf'
if __name__=='__main__':flash.main()
