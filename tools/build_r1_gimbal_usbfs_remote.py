"""Build normal-feature P7 USBFS integration; does not flash."""
from pathlib import Path
import json,hashlib,shutil
import build_r1_gimbal_wide as wide
build=wide.build
build.STEM='r1_gimbal_usbfs_remote';build.WORK=build.TOOLS/'r1-gimbal-usbfs-remote'
build.OUT=build.PROJECT/'知行回路软件/build/r1_gimbal_usbfs_remote'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_gimbal_usbfs_remote/main.c'
build.EXTRA_INCLUDE_DIRS += ['User/USB_Device','User/UART']
build.EXTRA_SOURCES += [Path('User/USB_Device/ch32v30x_usbfs_device.c'),Path('User/USB_Device/usb_desc.c'),Path('User/native_usb.c')]
old_prepare=build.PREPARE
def prepare():
    old_prepare()
    example=build.EVT/'USB/USBFS/DEVICE/SimulateCDC/User'
    shutil.copytree(example/'USB_Device',build.WORK/'User/USB_Device',dirs_exist_ok=True)
    (build.WORK/'User/UART').mkdir(exist_ok=True)
    shutil.copy2(example/'UART/UART.h',build.WORK/'User/UART/UART.h')
    p=build.WORK/'User/USB_Device/ch32v30x_usbfs_device.c'
    s=p.read_text(encoding='utf-8-sig');needle='case USBFS_UIS_TOKEN_OUT | DEF_UEP2:'
    assert s.count(needle)==1
    p.write_text(s.replace(needle,needle+'\n                        if(!(intst & USBFS_UIS_TOG_OK))break;'),encoding='utf-8')
build.PREPARE=prepare
if __name__=='__main__':
    build.main();p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
    d.update(date='2026-10-14',vid_pid='1A86:FE0C',port='P7 USBFS PA11/PA12',
        scope='Restore normal range/three OLED/warning/settings/ultrasonic; P7 read queries plus bounded manual gimbal allowlist; motor commands rejected; reset/suspend/3s lease stop; startup zero PWM',
        all_source_sha256={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in build.MAIN_SOURCE.parent.iterdir() if x.suffix in ('.c','.h')},
        flash='NOT_RUN',physical_usb='NOT_TESTED')
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
