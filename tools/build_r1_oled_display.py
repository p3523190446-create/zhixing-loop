"""Build the single-screen SSD1306 128x64 compatibility test; never flashes."""
from pathlib import Path
import hashlib
import json
import shutil
import build_r1_oled_probe as probe

build=probe.build
build.STEM='r1_oled_display'
build.WORK=build.TOOLS/'r1-oled-display'
build.OUT=build.PROJECT/'知行回路软件/build/r1_oled_display'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_oled_display/main.c'
build.EXTRA_SOURCES+=[Path('User/oled_display.c')]

def prepare():
    probe.prepare()
    for name in ['oled_display.c','oled_display.h','oled_glyphs.h']:
        shutil.copy2(build.MAIN_SOURCE.parent/name,build.WORK/'User'/name)

build.PREPARE=prepare
if __name__=='__main__':
    build.main()
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
    d['date']='2026-10-07'
    d['probe_source_sha256']=hashlib.sha256((build.MAIN_SOURCE.parent/'oled_probe.c').read_bytes()).hexdigest()
    d['uart_source_sha256']=hashlib.sha256((build.MAIN_SOURCE.parent/'vision_uart.c').read_bytes()).hexdigest()
    d['display_source_sha256']=hashlib.sha256((build.MAIN_SOURCE.parent/'oled_display.c').read_bytes()).hexdigest()
    d['glyph_source_sha256']=hashlib.sha256((build.MAIN_SOURCE.parent/'oled_glyphs.h').read_bytes()).hexdigest()
    d['scope']='Single OLED SSD1306 128x64 compatibility test; actual controller unconfirmed'
    d['physical_screen']='PENDING_USER_OBSERVATION'
    p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
