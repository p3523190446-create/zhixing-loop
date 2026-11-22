"""Build observed short tests using official M1/M2/M3/M4 numbering."""
from pathlib import Path
import json,hashlib
import build_r1_motor_probe as probe
build=probe.build
build.STEM='r1_motor_channels'
build.WORK=build.TOOLS/'r1-motor-channels'
build.OUT=build.PROJECT/'知行回路软件/build/r1_motor_channels'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_motor_channels/main.c'
if __name__=='__main__':
    build.main()
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
    d['date']='2026-10-08'
    d['all_source_sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in build.MAIN_SOURCE.parent.iterdir() if x.suffix in ('.c','.h')}
    d['scope']='Official M1LF/M2LR/M3RF/M4RR suspended-wheel tests: fixed PWM900,250ms stop deadline,3 zero stop frames; no automatic nonzero motion'
    p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
