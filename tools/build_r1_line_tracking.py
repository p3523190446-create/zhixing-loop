"""Build a static line acquisition overlay on the exact saved v8 User snapshot.
Does not flash or access devices. The old application's actuator gates remain intact.
"""
from pathlib import Path
import hashlib
import json
import shutil
import build_r1_official_tt_v8 as previous

build=previous.build
build.STEM='r1_line_tracking'
build.WORK=build.TOOLS/'r1-line-tracking'
build.OUT=build.PROJECT/'知行回路软件/build/r1_line_tracking'
BASE=build.PROJECT/'知行回路软件/build/r1_official_tt_v8/source-snapshot'
OVERLAY=build.PROJECT/'知行回路软件/board/r1_line_tracking'
build.EXTRA_SOURCES += [Path('User/line_protocol.c'),Path('User/line_tracking.c')]
prepare_dependencies=build.PREPARE

def edit(path,old,new):
    text=path.read_text(encoding='utf-8-sig')
    if text.count(old)!=1:raise RuntimeError(f'Expected one anchor in {path}: {old[:80]}')
    path.write_text(text.replace(old,new),encoding='utf-8')

def prepare():
    # Populate vendor ToF/USB source directories outside User, then restore the
    # exact deployed User baseline rather than relying on historical overlays.
    prepare_dependencies()
    u=build.WORK/'User'
    shutil.copytree(BASE,u,dirs_exist_ok=True)
    for p in OVERLAY.iterdir():
        if p.suffix in ('.c','.h'):shutil.copy2(p,u/p.name)
    edit(u/'main.c','#include "motor_probe.h"','#include "motor_probe.h"\n#include "line_tracking.h"')
    edit(u/'main.c','    motor_probe_init();','    motor_probe_init();\n    line_tracking_init(tick_ms);')
    edit(u/'main.c','        motor_probe_poll(tick_ms);','        motor_probe_poll(tick_ms);\n        line_tracking_poll(tick_ms);')
    edit(u/'vision_uart.c','#include "remote_drive.h"','#include "remote_drive.h"\n#include "line_tracking.h"')
    edit(u/'vision_uart.c','    if(remote_drive_uart_command(line,now,reply))return;',
         '    if(line_tracking_command(line,now,reply))return;\n    if(remote_drive_uart_command(line,now,reply))return;')
    edit(u/'vision_uart.c','"PING","STATUS","GIMBAL_STATUS","ULTRA_STATUS",',
         '"LINE_ID","LINE_STATUS","LINE_ANALOG","LINE_DIGITAL",\n        "PING","STATUS","GIMBAL_STATUS","ULTRA_STATUS",')
    edit(u/'remote_drive.c','R1_DRIVE_STARTUP_MANUAL_V8_20261023','R1_MANUAL_V8_LINE_STATIC_V1_20261025')

build.PREPARE=prepare
if __name__=='__main__':
    build.main()
    snap=build.OUT/'source-snapshot'
    shutil.copytree(build.WORK/'User',snap,dirs_exist_ok=True)
    changed=[p.relative_to(snap).as_posix() for p in snap.rglob('*') if p.is_file() and
             (not (BASE/p.relative_to(snap)).exists() or p.read_bytes()!=(BASE/p.relative_to(snap)).read_bytes())]
    assert sorted(changed)==sorted(['line_protocol.c','line_protocol.h','line_tracking.c','line_tracking.h',
                                    'main.c','vision_uart.c','remote_drive.c']),changed
    path=build.OUT/'build_result.json'
    result=json.loads(path.read_text(encoding='utf-8'))
    result.update(date='2026-10-25',scope='UART4 115200 PC10 TX/PC11 RX; eight raw channels and independent freshness; no line-based motion',
                  changed_sources_vs_v8=changed,flash='NOT_RUN',physical_line_sensor='NOT_RUN',
                  phone_ui='NOT_IMPLEMENTED',actuator_sources_unchanged=True,
                  all_source_sha256={p.relative_to(snap).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in snap.rglob('*') if p.is_file()})
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
