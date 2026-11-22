"""Measured loaded low-speed floor; manufacturer's PID/deadzone remain unchanged."""
import hashlib,json,shutil
import build_r1_official_tt_v5 as previous
build=previous.build;edit=previous.edit
build.STEM='r1_official_tt_v6';build.WORK=build.TOOLS/'r1-official-tt-v6'
build.OUT=build.PROJECT/'知行回路软件/build'/build.STEM
base_prepare=build.PREPARE
def prepare():
    base_prepare();u=build.WORK/'User'
    edit(u/'remote_drive.c','R1_DRIVE_STARTUP_MANUAL_V5_20261021','R1_DRIVE_STARTUP_MANUAL_V6_20261021')
    edit(u/'wheel_control.c','int outer=20+peak*100/250;if(wheel_fault)return wheel_fault;',
         'int outer=20+peak*100/250;if(outer<60)outer=60;if(wheel_fault)return wheel_fault;')
    edit(u/'wheel_control.c','if(wanted<10)sign=0;',
         '/* Real v5 loaded feedback: inner targets17..50 stopped and faulted.\n         * Keep the demonstrated60 working floor; a slower inner side is held at\n         * zero by driver PID while the outer side turns. No extra PWM kick. */\n        if(wanted<60)sign=0;')
build.PREPARE=prepare
if __name__=='__main__':
    build.main();snap=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snap,dirs_exist_ok=True)
    base=build.PROJECT/'知行回路软件/build/r1_official_tt_v5/source-snapshot'
    changed=[p.relative_to(snap).as_posix() for p in snap.rglob('*') if p.is_file() and (not (base/p.relative_to(snap)).exists() or p.read_bytes()!=(base/p.relative_to(snap)).read_bytes())]
    assert sorted(changed)==['remote_drive.c','wheel_control.c'],changed
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
    d.update(date='2026-10-21',scope='Official TT PID retained; actual loaded v5 targets17..50 sometimes stall while60 straight/pivot demonstrated. Minimum60 nonzero working target, slower inner wheel held0; no added PWM, protection retained',changed_sources_vs_v5=changed,flash='NOT_RUN',physical_acceptance='NOT_RUN',all_source_sha256={x.relative_to(snap).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snap.rglob('*') if x.suffix in ('.c','.h')})
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(d['binary_sha256'])
