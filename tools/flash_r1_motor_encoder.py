import flash_r1_motor_probe as flash
flash.OUT=flash.PROJECT/'知行回路软件/build/r1_motor_encoder'
flash.WORK=flash.TOOLS/'r1-motor-encoder'
flash.ELF=flash.WORK/'r1_motor_encoder.elf'
flash.BASE=flash.TOOLS/'r1-motor-channels/r1_motor_channels.elf'
if __name__=='__main__':flash.main()
