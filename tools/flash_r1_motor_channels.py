"""Install official-channel bench tests; installation does not start wheels."""
import flash_r1_motor_probe as flash
flash.OUT=flash.PROJECT/'知行回路软件/build/r1_motor_channels'
flash.WORK=flash.TOOLS/'r1-motor-channels'
flash.ELF=flash.WORK/'r1_motor_channels.elf'
flash.BASE=flash.TOOLS/'r1-motor-pulse/r1_motor_pulse.elf'
if __name__=='__main__':flash.main()
