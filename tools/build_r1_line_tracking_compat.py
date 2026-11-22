"""Retain the legacy drive identity; LINE_ID separately advertises line acquisition."""
import hashlib,json,shutil
import build_r1_line_tracking as previous
build=previous.build
build.STEM='r1_line_tracking_compat';build.WORK=build.TOOLS/'r1-line-tracking-compat'
build.OUT=build.PROJECT/'知行回路软件/build/r1_line_tracking_compat'
prepare_base=build.PREPARE
def prepare():
    prepare_base()
    previous.edit(build.WORK/'User/remote_drive.c','R1_MANUAL_V8_LINE_STATIC_V1_20261025','R1_DRIVE_STARTUP_MANUAL_V8_20261023')
build.PREPARE=prepare
if __name__=='__main__':
    build.main();snap=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snap,dirs_exist_ok=True)
    base=build.PROJECT/'知行回路软件/build/r1_line_tracking/source-snapshot'
    changed=[p.relative_to(snap).as_posix() for p in snap.rglob('*') if p.is_file() and
             (not (base/p.relative_to(snap)).exists() or p.read_bytes()!=(base/p.relative_to(snap)).read_bytes())]
    assert changed==['remote_drive.c'],changed
    path=build.OUT/'build_result.json';r=json.loads(path.read_text(encoding='utf-8'))
    r.update(date='2026-10-25',scope='Only restore v8 drive identity compatibility; LINE_ID remains the independent sensor feature ID',
             changed_sources_vs_line_v1=changed,flash='NOT_RUN',all_source_sha256={p.relative_to(snap).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in snap.rglob('*') if p.is_file()})
    path.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
