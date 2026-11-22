import flash_r1_motor_probe as flash
flash.OUT=flash.PROJECT/'知行回路软件/build/r1_motor_tuning'
flash.WORK=flash.TOOLS/'r1-motor-tuning'
flash.ELF=flash.WORK/'r1_motor_tuning.elf'
flash.BASE=flash.TOOLS/'r1-motor-closed-loop/r1_motor_closed_loop.elf'
if __name__=='__main__':flash.main()
