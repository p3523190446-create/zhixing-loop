"""Compile encoder input probe, preserving triple OLED and range guard; never flashes."""
from pathlib import Path
import hashlib,json,shutil
import build_r1_oled_display as display
build=display.build
build.STEM='r1_distance_trend'
build.WORK=build.TOOLS/'r1-distance-trend'
build.OUT=build.PROJECT/'知行回路软件/build/r1_distance_trend'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_distance_trend/main.c'
build.EXTRA_SOURCES += [Path('User/oled_probe2.c'),Path('User/oled_display2.c'),Path('User/oled_probe3.c'),Path('User/oled_display3.c')]
def prepare():
 display.prepare()
 for name in ['vl53l0x_platform.c','vl53l0x_platform.h','oled_probe2.c','oled_probe2.h','oled_display2.c','oled_display2.h','vision_labels.h','oled_probe3.c','oled_probe3.h','oled_display3.c','oled_display3.h','vision_status.h','encoder_decode.h','warning_adjust.h','distance_trend.h']:
  shutil.copy2(build.MAIN_SOURCE.parent/name,build.WORK/'User'/name)
build.PREPARE=prepare
if __name__=='__main__':
 build.main()
 p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
 d['date']='2026-10-08'
 d['all_source_sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in build.MAIN_SOURCE.parent.iterdir() if x.suffix in ['.c','.h']}
 d['scope']='Distance trend indication on OLED1 only; no change to warning or motion control'
 d['physical_reconnect']='NOT_RUN'
 p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
