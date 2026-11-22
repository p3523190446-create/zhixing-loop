"""Compile encoder input probe, preserving triple OLED and range guard; never flashes."""
from pathlib import Path
import hashlib,json,shutil
import build_r1_oled_display as display
build=display.build
build.STEM='r1_settings_records'
build.WORK=build.TOOLS/'r1-settings-records'
build.OUT=build.PROJECT/'知行回路软件/build/r1_settings_records'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_settings_records/main.c'
build.EXTRA_SOURCES += [Path('User/oled_probe2.c'),Path('User/oled_display2.c'),Path('User/oled_probe3.c'),Path('User/oled_display3.c'),Path('User/storage_probe.c'),Path('User/settings.c')]
def prepare():
 display.prepare()
 for name in ['vl53l0x_platform.c','vl53l0x_platform.h','oled_probe2.c','oled_probe2.h','oled_display2.c','oled_display2.h','vision_labels.h','oled_probe3.c','oled_probe3.h','oled_display3.c','oled_display3.h','vision_status.h','encoder_decode.h','warning_adjust.h','distance_trend.h','mute_key.h','storage_probe.c','storage_probe.h','user_key.h','settings.c','settings.h','settings_codec.h']:
  shutil.copy2(build.MAIN_SOURCE.parent/name,build.WORK/'User'/name)
build.PREPARE=prepare
if __name__=='__main__':
 build.main()
 p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
 d['date']='2026-10-08'
 d['all_source_sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in build.MAIN_SOURCE.parent.iterdir() if x.suffix in ['.c','.h']}
 d['scope']='Physical long-USER saves distance and sound mode together; v1 migration, v2 CRC and dual-sector commit'
 d['physical_reconnect']='NOT_RUN'
 p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
