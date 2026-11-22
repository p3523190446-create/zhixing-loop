"""Build separate USBFS diagnostic from WCH SimulateCDC; NEVER flashes."""
from pathlib import Path
import json,hashlib,shutil
import build_r1_bringup as build
build.STEM='r1_native_usb_probe';build.WORK=build.TOOLS/'r1-native-usb-probe'
build.OUT=build.PROJECT/'知行回路软件/build/r1_native_usb_probe'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_native_usb_probe/main.c'
build.EXTRA_INCLUDE_DIRS=['User/USB_Device','User/UART']
build.EXTRA_SOURCES=[Path('User/USB_Device/ch32v30x_usbfs_device.c'),Path('User/USB_Device/usb_desc.c'),Path('User/native_usb.c')]
def prepare():
    example=build.EVT/'USB/USBFS/DEVICE/SimulateCDC/User'
    shutil.copytree(example/'USB_Device',build.WORK/'User/USB_Device',dirs_exist_ok=True)
    (build.WORK/'User/UART').mkdir(exist_ok=True)
    shutil.copy2(example/'UART/UART.h',build.WORK/'User/UART/UART.h')
    shutil.copy2(build.MAIN_SOURCE.parent/'native_usb.c',build.WORK/'User/native_usb.c')
    usb=build.WORK/'User/USB_Device/ch32v30x_usbfs_device.c'
    text=usb.read_text(encoding='utf-8-sig')
    old='case USBFS_UIS_TOKEN_OUT | DEF_UEP2:'
    assert text.count(old)==1
    # Do not enqueue duplicate or invalid-toggle OUT packets.
    text=text.replace(old,old+'\n                        if(!(intst & USBFS_UIS_TOG_OK))break;')
    usb.write_text(text,encoding='utf-8')
build.PREPARE=prepare
if __name__=='__main__':
    build.main()
    path=build.OUT/'build_result.json';record=json.loads(path.read_text(encoding='utf-8'))
    record.update(date='2026-10-13',scope='Standalone P7 USBFS diagnostic; PING/NATIVE_ID/3 fixed echo tokens only; NO motor/servo control or physical UART2',
        vid_pid='1A86:FE0C',port='R1 P7 USBFS PA11/PA12',existing_sensor_oled_features='NOT_INITIALIZED_IN_THIS_DIAGNOSTIC',
        vendor_source='WCH EVT SimulateCDC USBFS; WCH-only copyright retained',flash='NOT_RUN',physical_usb='NOT_TESTED',
        all_source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in build.MAIN_SOURCE.parent.glob('*.c')})
    path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
