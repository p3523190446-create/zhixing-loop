"""Build normal-feature P7 USBFS integration; does not flash."""
from pathlib import Path
import json,hashlib,shutil
import build_r1_gimbal_wide as wide
build=wide.build
build.STEM='r1_usbhs_camera_bridge_usb_lifecycle';build.WORK=build.TOOLS/'r1-usbhs-camera-bridge-usb-lifecycle'
build.OUT=build.PROJECT/'知行回路软件/build/r1_usbhs_camera_bridge_usb_lifecycle'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_usbhs_camera_bridge_usb_lifecycle/main.c'
build.EXTRA_INCLUDE_DIRS += ['User/USB_Device','User/UART']
build.EXTRA_SOURCES += [Path('User/USB_Device/ch32v30x_usbfs_device.c'),Path('User/USB_Device/usb_desc.c'),Path('User/native_usb.c')]
build.EXTRA_FLAGS += ['-DUSBHS_MAX_PACKET_SIZE=512']
build.EXTRA_INCLUDE_DIRS += ['User/USB_Host']
build.EXTRA_SOURCES += [Path('User/USB_Host/ch32v30x_usbhs_host.c'),Path('User/uvc_bridge.c')]
old_prepare=build.PREPARE
def prepare():
    old_prepare()
    shutil.copytree(build.EVT/'USB/USBHS/HOST_KM/User/USB_Host',build.WORK/'User/USB_Host',dirs_exist_ok=True)
    example=build.EVT/'USB/USBFS/DEVICE/SimulateCDC/User'
    shutil.copytree(example/'USB_Device',build.WORK/'User/USB_Device',dirs_exist_ok=True)
    (build.WORK/'User/UART').mkdir(exist_ok=True)
    shutil.copy2(example/'UART/UART.h',build.WORK/'User/UART/UART.h')
    p=build.WORK/'User/USB_Device/ch32v30x_usbfs_device.c'
    shutil.copy2(build.MAIN_SOURCE.parent/'ch32v30x_usbfs_device.c',p)
    shutil.copy2(build.MAIN_SOURCE.parent/'usbfs_lifecycle.h',build.WORK/'User/usbfs_lifecycle.h')
build.PREPARE=prepare
if __name__=='__main__':
    build.main();p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
    d.update(date='2026-10-14',vid_pid='1A86:FE0C',port='P7 USBFS PA11/PA12',
        scope='Normal range remapped J4 PD14/PD15, three OLED/warning/settings/ultrasonic; P6 USBHS UVC MJPEG 160x120 at negotiated 5fps, bounded 8KiB frame; P7 frame chunks and manual gimbal allowlist; motor commands rejected; reset/suspend/3s gimbal lease stop; startup zero PWM; phone preview rate not yet verified',
        all_source_sha256={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in build.MAIN_SOURCE.parent.iterdir() if x.suffix in ('.c','.h')},
        flash='NOT_RUN',physical_usb='NOT_TESTED',usb_lifecycle='USB starts before ToF init; SET_CONFIG0/1 and SET_INTERFACE0 strict validation and DATA0 reset; not a certified fix for missing Android enumeration')
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
