from pathlib import Path
import json,hashlib
import build_r1_motor_probe as probe
build=probe.build
build.STEM='r1_gimbal_wide';build.WORK=build.TOOLS/'r1-gimbal-wide'
build.OUT=build.PROJECT/'知行回路软件/build/r1_gimbal_wide'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_gimbal_wide/main.c'
build.EXTRA_SOURCES += [Path('User/ultrasonic.c'),Path('User/servo_probe.c'),Path('SRC/Peripheral/src/ch32v30x_exti.c')]
if __name__=='__main__':
    build.main();p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
    d['date']='2026-10-13'
    d['all_source_sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in build.MAIN_SOURCE.parent.iterdir() if x.suffix in ('.c','.h')}
    d['scope']='Manual gimbal target control in verified pulse bounds; slew1us/10ms; 3s keepalive; no arm on reconnect; only motor read queries and STOP allowed'
    d['flash']='NOT_RUN';d['manual_ui_physical']='NOT_RUN'
    p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
