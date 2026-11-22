"""Recover idle missed profile / upload without rearming motion."""
import hashlib,json,shutil
import build_r1_official_tt_v7 as previous
build=previous.build;edit=previous.edit
build.STEM='r1_official_tt_v8';build.WORK=build.TOOLS/'r1-official-tt-v8'
build.OUT=build.PROJECT/'知行回路软件/build'/build.STEM
base_prepare=build.PREPARE
def prepare():
    base_prepare();u=build.WORK/'User'
    shutil.copy2(build.PROJECT/'知行回路软件/board/r1_official_tt_full_speed/driver_recovery.h',u/'driver_recovery.h')
    edit(u/'remote_drive.c','R1_DRIVE_STARTUP_MANUAL_V7_20261023','R1_DRIVE_STARTUP_MANUAL_V8_20261023')
    edit(u/'motor_probe.c','void motor_probe_poll(uint32_t now)','\n#include "driver_recovery.h"\n\nvoid motor_probe_poll(uint32_t now)')
    edit(u/'motor_probe.c','    startup_hold_poll(now);','    motor_profile_recovery_poll(now);\n    startup_hold_poll(now);')
build.PREPARE=prepare
if __name__=='__main__':
    build.main();snap=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snap,dirs_exist_ok=True)
    base=build.PROJECT/'知行回路软件/build/r1_official_tt_v7/source-snapshot'
    changed=[p.relative_to(snap).as_posix() for p in snap.rglob('*') if p.is_file() and (not (base/p.relative_to(snap)).exists() or p.read_bytes()!=(base/p.relative_to(snap)).read_bytes())]
    assert sorted(changed)==['driver_recovery.h','motor_probe.c','remote_drive.c'],changed
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
    d.update(date='2026-10-23',scope='v7 full1000 speed preserved; idle-only read-only actual-profile/passive-upload retry every5s,150ms silence,capture validator; never autoARM, no persistent driver writes',changed_sources_vs_v7=changed,flash='NOT_RUN',physical_acceptance='NOT_RUN',all_source_sha256={x.relative_to(snap).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snap.rglob('*') if x.suffix in ('.c','.h')})
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(d['binary_sha256'])
