"""Install fixed Q1 bench pulse; installing does not trigger nonzero motion."""
import flash_r1_motor_probe as flash
flash.OUT=flash.PROJECT/'知行回路软件/build/r1_motor_pulse'
flash.WORK=flash.TOOLS/'r1-motor-pulse'
flash.ELF=flash.WORK/'r1_motor_pulse.elf'
flash.BASE=flash.TOOLS/'r1-motor-probe/r1_motor_probe.elf'
if __name__=='__main__':flash.main()
