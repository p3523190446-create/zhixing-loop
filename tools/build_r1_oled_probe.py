"""Compile only: isolated OLED I2C probe alongside the working vision receiver."""
from pathlib import Path
import hashlib
import json
import shutil
import build_r1_vision_bridge as vision

build=vision.build
build.STEM='r1_oled_probe'
build.WORK=build.TOOLS/'r1-oled-probe'
build.OUT=build.PROJECT/'知行回路软件/build/r1_oled_probe'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_oled_probe/main.c'
build.EXTRA_SOURCES+=[Path('User/oled_probe.c')]

def prepare():
    vision.guard.prepare()
    for name in ('vision_uart.h','vision_uart.c'):
        shutil.copy2(build.MAIN_SOURCE.parent/name,build.WORK/'User'/name)
    for name in ('oled_probe.h','oled_probe.c'):
        shutil.copy2(build.MAIN_SOURCE.parent/name,build.WORK/'User'/name)

build.PREPARE=prepare
if __name__=='__main__':
    build.main()
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
    d['date']='2026-10-07'
    d['probe_source_sha256']=hashlib.sha256((build.MAIN_SOURCE.parent/'oled_probe.c').read_bytes()).hexdigest()
    d['uart_source_sha256']=hashlib.sha256((build.MAIN_SOURCE.parent/'vision_uart.c').read_bytes()).hexdigest()
    d['scope']='OLED I2C ACK probe only, PB8/PB9; no controller or resolution claim'
    d['oled_physical']='NOT_RUN';d['display_render']='NOT_IMPLEMENTED'
    p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
