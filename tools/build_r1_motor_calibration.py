import json,hashlib
import build_r1_motor_probe as probe
build=probe.build
build.STEM='r1_motor_calibration'
build.WORK=build.TOOLS/'r1-motor-calibration'
build.OUT=build.PROJECT/'知行回路软件/build/r1_motor_calibration'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_motor_calibration/main.c'
if __name__=='__main__':
    build.main()
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
    d['date']='2026-10-08'
    d['all_source_sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in build.MAIN_SOURCE.parent.iterdir() if x.suffix in ('.c','.h')}
    d['scope']='Fixed per-wheel PWM25/300/700 calibration pulses1.2s; sample400-1000ms; preserves previous speed test'
    p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
