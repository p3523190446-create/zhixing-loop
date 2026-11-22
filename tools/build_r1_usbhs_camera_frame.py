"""Prepare USBHS camera descriptor probe. Compilation only; no device access."""
from pathlib import Path
import shutil,json,hashlib
import build_r1_bringup as build
build.STEM='r1_usbhs_camera_frame'
build.WORK=build.TOOLS/'r1-usbhs-camera-frame'
build.OUT=build.PROJECT/'知行回路软件/build/r1_usbhs_camera_frame'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_usbhs_camera_frame/main.c'
build.EXTRA_INCLUDE_DIRS=['User/USB_Host']
build.EXTRA_FLAGS=['-DUSBHS_MAX_PACKET_SIZE=512']
build.EXTRA_SOURCES=[Path('User/USB_Host/ch32v30x_usbhs_host.c')]
def prepare():
    shutil.copytree(build.EVT/'USB/USBHS/HOST_KM/User/USB_Host',build.WORK/'User/USB_Host',dirs_exist_ok=True)
build.PREPARE=prepare
if __name__=='__main__':
    build.main();p=build.OUT/'build_result.json';r=json.loads(p.read_text(encoding='utf8'))
    r.update(date='2026-10-14',scope='Isolated USBHS P6 one bounded160x120 MJPEG frame; no video relay and no motor/servo commands',
             all_source_sha256={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in build.MAIN_SOURCE.parent.iterdir() if x.suffix in ('.c','.h')},
             hardware_prerequisite='Disconnect sensor leads PB6/PB7; motor battery and servo supplies off; P9 PC only power/debug; P7 empty',
             physical_camera='NOT_TESTED',flash='NOT_RUN',video_forwarding='NOT_IMPLEMENTED',normal_features='TEMPORARILY_NOT_RUNNING_IN_THIS_DIAGNOSTIC',
             vendor_sources={str(x.relative_to(build.WORK)):hashlib.sha256(x.read_bytes()).hexdigest() for x in (build.WORK/'User/USB_Host').glob('*') if x.is_file()})
    p.write_text(json.dumps(r,indent=2),encoding='utf8')
