"""Explicit speed-control capability v2; old Android PWM-only drive stays gated."""
import hashlib,json,shutil
import build_r1_drive_startup_stable as previous
build=previous.build;build.STEM='r1_drive_startup_stable_v2';build.WORK=build.TOOLS/'r1-drive-startup-stable-v2';build.OUT=build.PROJECT/'知行回路软件/build/r1_drive_startup_stable_v2'
base_prepare=build.PREPARE
def prepare():
    base_prepare();p=build.WORK/'User/remote_drive.c'
    previous.previous.edit(p,'R1_DRIVE_STARTUP_STABLE_20261021','R1_DRIVE_STARTUP_STABLE_V2_20261021')
    previous.previous.edit(p,'DRIVE_CAPS,1,250,600','DRIVE_CAPS,2,250,600')
build.PREPARE=prepare
if __name__=='__main__':
    build.main();snapshot=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snapshot,dirs_exist_ok=True)
    baseline=build.PROJECT/'知行回路软件/build/r1_drive_startup_stable/source-snapshot'
    changed=[p.relative_to(snapshot).as_posix() for p in snapshot.rglob('*') if p.is_file() and (not (baseline/p.relative_to(snapshot)).exists() or p.read_bytes()!=(baseline/p.relative_to(snapshot)).read_bytes())]
    assert changed==['remote_drive.c'],changed
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
    d.update(date='2026-10-21',scope='Speed capabilityv2 gates old PWM-only Android; stable raw80..120 controller/375PWM300ms startup unchanged',changed_sources=changed,flash='NOT_RUN',physical_acceptance='NOT_RUN',all_source_sha256={x.relative_to(snapshot).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snapshot.rglob('*') if x.suffix in ('.c','.h')})
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(d['binary_sha256'])
