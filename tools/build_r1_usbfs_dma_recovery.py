"""Compile candidate RX ring/DMA reset repair; never accesses a device."""
from pathlib import Path
import json,hashlib
import build_r1_usbhs_camera_bridge_usb_lifecycle as previous
build=previous.build
build.STEM='r1_usbfs_dma_recovery'
build.WORK=build.TOOLS/'r1-usbfs-dma-recovery'
build.OUT=build.PROJECT/'知行回路软件/build/r1_usbfs_dma_recovery'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_usbfs_dma_recovery/main.c'
if __name__=='__main__':
 build.main()
 p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
 d.update(date='2026-10-20',scope='Candidate repair only: RX DMA and queue indices reset to same slot on SET_INTERFACE/SET_CONFIGURATION; normal features unchanged; motor commands rejected',all_source_sha256={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in build.MAIN_SOURCE.parent.iterdir() if x.suffix in ('.c','.h')},flash='NOT_RUN',physical_usb='NOT_TESTED',current_phone_fault_cause='NOT_DETERMINED')
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
