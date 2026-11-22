"""Compile PA8 one-axis trial, preserving ultrasonic bench features."""
from pathlib import Path
import json,hashlib
import build_r1_motor_probe as probe
build=probe.build
build.STEM='r1_servo_probe';build.WORK=build.TOOLS/'r1-servo-probe'
build.OUT=build.PROJECT/'知行回路软件/build/r1_servo_probe'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_servo_probe/main.c'
build.EXTRA_SOURCES += [Path('User/ultrasonic.c'),Path('User/servo_probe.c'),Path('SRC/Peripheral/src/ch32v30x_exti.c')]
if __name__=='__main__':
    build.main();p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
    d['date']='2026-10-13'
    d['all_source_sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in build.MAIN_SOURCE.parent.iterdir() if x.suffix in ('.c','.h')}
    d['scope']='PA8/TIM1 50Hz; boot zero pulse; CENTER/WIGGLE 1s or WIDE 2.5s fixed pulse sequences; TIM2 ends pulses independently of main loop; motors rejected except STOP'
    d['flash']='NOT_RUN';d['servo_physical']='NOT_RUN'
    p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
