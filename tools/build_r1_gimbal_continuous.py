"""Build continuous bounded random gimbal with live keepalive. No hardware."""
from pathlib import Path
import json,hashlib
import build_r1_motor_probe as probe
build=probe.build
build.STEM='r1_gimbal_continuous';build.WORK=build.TOOLS/'r1-gimbal-continuous'
build.OUT=build.PROJECT/'知行回路软件/build/r1_gimbal_continuous'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_gimbal_continuous/main.c'
build.EXTRA_SOURCES += [Path('User/ultrasonic.c'),Path('User/servo_probe.c'),Path('SRC/Peripheral/src/ch32v30x_exti.c')]
if __name__=='__main__':
    build.main();p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
    d['date']='2026-10-13'
    d['all_source_sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in build.MAIN_SOURCE.parent.iterdir() if x.suffix in ('.c','.h')}
    d['scope']='Explicit continuous random yaw1300..1700us/pitch1350..1650us, 1us per10ms; 3s keepalive expiry; boot zero; no vehicle motion'
    d['flash']='NOT_RUN';d['gimbal_physical']='NOT_RUN'
    p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
