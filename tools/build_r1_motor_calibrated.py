import json,hashlib
import build_r1_motor_probe as probe
build=probe.build
build.STEM='r1_motor_calibrated'
build.WORK=build.TOOLS/'r1-motor-calibrated'
build.OUT=build.PROJECT/'知行回路软件/build/r1_motor_calibrated'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_motor_calibrated/main.c'
if __name__=='__main__':
    build.main()
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
    d['date']='2026-10-08'
    d['all_source_sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in build.MAIN_SOURCE.parent.iterdir() if x.suffix in ('.c','.h')}
    d['scope']='Per-wheel estimated80mm/s holding drive from measured150/200 profiles; kick350PWM250ms then gradual control; acceptance pending'
    p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
