"""Build additive P9 USB diagnostics; never accesses a device."""
import json,hashlib
import build_r1_usbfs_dma_recovery as previous
build=previous.build
build.STEM='r1_usbfs_trace';build.WORK=build.TOOLS/'r1-usbfs-trace'
build.OUT=build.PROJECT/'知行回路软件/build/r1_usbfs_trace'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_usbfs_trace/main.c'
if __name__=='__main__':
 build.main()
 p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
 d.update(date='2026-10-20',scope='Additive read-only P9 USB_STATUS observer; deployed DMA fix preserved; no endpoint or motion behavior change',all_source_sha256={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in build.MAIN_SOURCE.parent.iterdir() if x.suffix in ('.c','.h')},flash='NOT_RUN',physical_usb='NOT_TESTED')
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
