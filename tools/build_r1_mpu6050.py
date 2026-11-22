"""Overlay static MPU telemetry on the exact deployed line-compat User snapshot."""
from pathlib import Path
import hashlib,json,shutil,sys
import build_r1_line_tracking_compat as previous
build=previous.build
build.STEM='r1_mpu6050_diag' if '--diag' in sys.argv else 'r1_mpu6050'
build.WORK=build.TOOLS/build.STEM.replace('_','-')
build.OUT=build.PROJECT/'知行回路软件/build'/build.STEM
BASE=build.PROJECT/'知行回路软件/build/r1_line_tracking_compat/source-snapshot'
OVERLAY=build.PROJECT/'知行回路软件/board/r1_mpu6050'
dependencies=build.PREPARE
build.EXTRA_SOURCES += [Path('User/mpu6050_probe.c')]
def edit(path,old,new):
    s=path.read_text(encoding='utf-8-sig');assert s.count(old)==1,(path,old)
    path.write_text(s.replace(old,new),encoding='utf-8')
def prepare():
    dependencies();u=build.WORK/'User';shutil.copytree(BASE,u,dirs_exist_ok=True)
    for p in OVERLAY.iterdir():
        if p.suffix in ('.c','.h'):shutil.copy2(p,u/p.name)
    edit(u/'main.c','#include "line_tracking.h"','#include "line_tracking.h"\n#include "mpu6050_probe.h"')
    edit(u/'main.c','    line_tracking_init(tick_ms);','    line_tracking_init(tick_ms);\n    mpu6050_probe_init(tick_ms);')
    edit(u/'main.c','        line_tracking_poll(tick_ms);','        line_tracking_poll(tick_ms);\n        mpu6050_probe_poll(tick_ms);')
    edit(u/'vision_uart.c','#include "line_tracking.h"','#include "line_tracking.h"\n#include "mpu6050_probe.h"')
    edit(u/'vision_uart.c','    if(line_tracking_command(line,now,reply))return;',
         '    if(mpu6050_probe_command(line,now,reply))return;\n    if(line_tracking_command(line,now,reply))return;')
    edit(u/'vision_uart.c','"LINE_ID","LINE_STATUS","LINE_ANALOG","LINE_DIGITAL",',
         '"MPU_ID","MPU_STATUS","MPU_RAW","MPU_DIAG",\n        "LINE_ID","LINE_STATUS","LINE_ANALOG","LINE_DIGITAL",')
build.PREPARE=prepare
if __name__=='__main__':
    build.main();snap=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snap,dirs_exist_ok=True)
    changed=[p.relative_to(snap).as_posix() for p in snap.rglob('*') if p.is_file() and
             (not (BASE/p.relative_to(snap)).exists() or p.read_bytes()!=(BASE/p.relative_to(snap)).read_bytes())]
    assert sorted(changed)==['main.c','mpu6050_probe.c','mpu6050_probe.h','vision_uart.c'],changed
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
    d.update(date='2026-10-25',scope='Static MPU6050 PD6/PD7 addr0x69,20Hz raw acquisition; line-compat actuators unchanged',
        changed_sources_vs_line_compat=changed,all_source_sha256={p.relative_to(snap).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in snap.rglob('*') if p.is_file()},
        physical_mpu='NOT_RUN',flash='NOT_RUN')
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
