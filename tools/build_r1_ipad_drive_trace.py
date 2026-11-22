"""Integrate existing bounded drive overlay on deployed USB trace baseline."""
from pathlib import Path
import hashlib,json,shutil
import build_r1_ipad_drive as previous
build=previous.build
build.STEM='r1_ipad_drive_trace';build.WORK=build.TOOLS/'r1-ipad-drive-trace'
build.OUT=build.PROJECT/'知行回路软件/build/r1_ipad_drive_trace'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_usbfs_trace/main.c'
if __name__=='__main__':
 build.main()
 snapshot=build.OUT/'source-snapshot'
 shutil.copytree(build.WORK/'User',snapshot,dirs_exist_ok=True)
 p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
 d.update(date='2026-10-20',scope='Existing four-drive BENCH overlay on deployed USB trace+DMA baseline; zero on boot,600ms lease,range/feedback gates; no hardware access by build',flash='NOT_RUN',physical_acceptance='NOT_RUN',ground_drive='NOT_VERIFIED',driver_wire_disconnect_stop='KNOWN_UNRESOLVED',all_source_sha256={x.relative_to(snapshot).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snapshot.rglob('*') if x.suffix in ('.c','.h')})
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(d['binary_sha256'])
