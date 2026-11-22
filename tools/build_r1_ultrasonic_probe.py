"""Compile fixed-forward ultrasonic bench variant. No device access."""
from pathlib import Path
import json,hashlib
import build_r1_motor_probe as probe
build=probe.build
build.STEM='r1_ultrasonic_probe'
build.WORK=build.TOOLS/'r1-ultrasonic-probe'
build.OUT=build.PROJECT/'知行回路软件/build/r1_ultrasonic_probe'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_ultrasonic_probe/main.c'
build.EXTRA_SOURCES += [Path('User/ultrasonic.c'),Path('SRC/Peripheral/src/ch32v30x_exti.c')]
if __name__=='__main__':
    build.main()
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
    d['date']='2026-10-13'
    d['all_source_sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in build.MAIN_SOURCE.parent.iterdir() if x.suffix in ('.c','.h')}
    d['scope']='PD12 trigger / PD13 EXTI13 echo; TIM4 1MHz; TIM2 timeout; original OLED/ToF/USER retained; motor commands rejected except STOP'
    d['flash']='NOT_RUN';d['ultrasonic_physical']='NOT_RUN'
    p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
