"""Expose the official full speed command range instead of the filming120 cap."""
import hashlib,json,shutil
import build_r1_official_tt_v6 as previous
build=previous.build;edit=previous.edit
build.STEM='r1_official_tt_v7';build.WORK=build.TOOLS/'r1-official-tt-v7'
build.OUT=build.PROJECT/'知行回路软件/build'/build.STEM
base_prepare=build.PREPARE
def prepare():
    base_prepare();u=build.WORK/'User'
    shutil.copy2(build.PROJECT/'知行回路软件/board/r1_official_tt_full_speed/wheel_control.c',u/'wheel_control.c')
    edit(u/'remote_drive.c','R1_DRIVE_STARTUP_MANUAL_V6_20261021','R1_DRIVE_STARTUP_MANUAL_V7_20261023')
    edit(u/'remote_drive.c','DRIVE_CAPS,3,250,600','DRIVE_CAPS,4,250,600')
    edit(u/'remote_drive.c','DRIVE_LIMITS,3600,0,0,120','DRIVE_LIMITS,3600,0,0,1000')
build.PREPARE=prepare
if __name__=='__main__':
    build.main();snap=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snap,dirs_exist_ok=True)
    base=build.PROJECT/'知行回路软件/build/r1_official_tt_v6/source-snapshot'
    changed=[p.relative_to(snap).as_posix() for p in snap.rglob('*') if p.is_file() and (not (base/p.relative_to(snap)).exists() or p.read_bytes()!=(base/p.relative_to(snap)).read_bytes())]
    assert sorted(changed)==['remote_drive.c','wheel_control.c'],changed
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
    d.update(date='2026-10-23',scope='Official +/-1000 native speed range, linear normalized250 to1000, rising1000/s slew,1250 engineering overspeed guard, protocol4 advertises1000; manufacturer default profile/PID and all stop/lease/voltage/UART guards retained',changed_sources_vs_v6=changed,flash='NOT_RUN',physical_acceptance='NOT_RUN',all_source_sha256={x.relative_to(snap).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snap.rglob('*') if x.suffix in ('.c','.h')})
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(d['binary_sha256'])
