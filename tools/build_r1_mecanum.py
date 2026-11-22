"""Build from the preserved deployed IMU source snapshot, without flashing."""
from pathlib import Path
import hashlib,json,shutil
import build_r1_imu_observer as previous
build=previous.build
BASE=build.PROJECT/'知行回路软件/build/r1_imu_observer/source-snapshot'
BASE_WORK=build.WORK
OVERLAY=build.PROJECT/'知行回路软件/board/r1_mecanum'
build.STEM='r1_mecanum';build.WORK=build.TOOLS/'r1-mecanum'
build.OUT=build.PROJECT/'知行回路软件/build/r1_mecanum'
build.EXTRA_SOURCES += [Path('User/mecanum_mix.c')]

def prepare():
    expected=json.loads((OVERLAY/'baseline-sha256.json').read_text(encoding='utf-8'))
    for rel,sha in expected.items():
        assert hashlib.sha256((build.PROJECT/'知行回路软件'/rel).read_bytes()).hexdigest()==sha,rel
    for name in ('ST_API','GuardCore'):
        shutil.copytree(BASE_WORK/name,build.WORK/name,dirs_exist_ok=True)
    shutil.copytree(BASE,build.WORK/'User',dirs_exist_ok=True)
    for p in OVERLAY.iterdir():
        if p.suffix in ('.c','.h'):shutil.copy2(p,build.WORK/'User'/p.name)

build.PREPARE=prepare
if __name__=='__main__':
    build.main();snap=build.OUT/'source-snapshot'
    shutil.copytree(build.WORK/'User',snap,dirs_exist_ok=True)
    changed=sorted(p.relative_to(snap).as_posix() for p in snap.rglob('*') if p.is_file() and
       (not (BASE/p.relative_to(snap)).exists() or p.read_bytes()!=(BASE/p.relative_to(snap)).read_bytes()))
    assert changed==['mecanum_mix.c','mecanum_mix.h','remote_drive.c','wheel_control.c','wheel_control.h'],changed
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
    d.update(date='2026-10-26',scope='Mecanum body vector, 4 independent speed targets, existing safety and sensor code retained',
      changed_sources_vs_deployed_imu=changed,flash='NOT_RUN',physical_acceptance='NOT_RUN',
      all_source_sha256={x.relative_to(snap).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snap.rglob('*') if x.is_file()})
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
