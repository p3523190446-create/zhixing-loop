"""Build the existing dashboard with EC11 input removed. No hardware access."""
from pathlib import Path
import json,hashlib
import build_r1_motor_probe as probe
build=probe.build
build.STEM='r1_motor_dashboard_no_knob'
build.WORK=build.TOOLS/'r1-motor-dashboard-no-knob'
build.OUT=build.PROJECT/'知行回路软件/build/r1_motor_dashboard_no_knob'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_motor_dashboard_no_knob/main.c'
if __name__=='__main__':
    build.main()
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
    d['date']='2026-10-12'
    d['all_source_sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in build.MAIN_SOURCE.parent.iterdir() if x.suffix in ('.c','.h')}
    d['scope']='EC11 removed; no PD4/PD5 reads/drives, no knob distance edits; saved settings and USER handling retained'
    d['flash']='NOT_RUN'
    p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
