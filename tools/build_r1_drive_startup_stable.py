"""Avoid the measured intermittent-stall low target band; preserve startup guards."""
import hashlib,json,shutil
import build_r1_drive_startup as previous
build=previous.build;build.STEM='r1_drive_startup_stable';build.WORK=build.TOOLS/'r1-drive-startup-stable';build.OUT=build.PROJECT/'知行回路软件/build/r1_drive_startup_stable'
base_prepare=build.PREPARE
def prepare():
    base_prepare();previous.edit(build.WORK/'User/remote_drive.c','R1_DRIVE_STARTUP_20261021','R1_DRIVE_STARTUP_STABLE_20261021')
build.PREPARE=prepare
if __name__=='__main__':
    build.main();snapshot=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snapshot,dirs_exist_ok=True)
    baseline=build.PROJECT/'知行回路软件/build/r1_drive_startup/source-snapshot'
    changed=[p.relative_to(snapshot).as_posix() for p in snapshot.rglob('*') if p.is_file() and (not (baseline/p.relative_to(snapshot)).exists() or p.read_bytes()!=(baseline/p.relative_to(snapshot)).read_bytes())]
    assert sorted(changed)==['remote_drive.c','wheel_control.c'],changed
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
    d.update(date='2026-10-21',scope='Same375PWM300ms per-wheel startup/PI/stall guards; raw speed target80..120 avoids measured48-target intermittent zero; suspended only',changed_sources=changed,flash='NOT_RUN',physical_acceptance='NOT_RUN',all_source_sha256={x.relative_to(snapshot).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snapshot.rglob('*') if x.suffix in ('.c','.h')})
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(d['binary_sha256'])
