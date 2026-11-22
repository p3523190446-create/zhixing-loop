"""Build a UART receiver alongside the existing independent distance warning."""
from pathlib import Path
import hashlib
import json
import shutil
import build_r1_distance_guard as guard

build = guard.build
build.STEM = 'r1_vision_bridge'
build.WORK = build.TOOLS / 'r1-vision-bridge'
build.OUT = build.PROJECT / '知行回路软件/build/r1_vision_bridge'
build.MAIN_SOURCE = build.PROJECT / '知行回路软件/board/r1_vision_bridge/main.c'
build.EXTRA_SOURCES += [Path('User/vision_uart.c')]

def prepare():
    guard.prepare()
    for name in ('vision_uart.h', 'vision_uart.c'):
        shutil.copy2(build.MAIN_SOURCE.parent / name, build.WORK / 'User' / name)

build.PREPARE = prepare

if __name__ == '__main__':
    build.main()
    p = build.OUT / 'build_result.json'
    record = json.loads(p.read_text(encoding='utf-8'))
    record['date'] = '2026-10-07'
    record['uart_source_sha256'] = hashlib.sha256((build.MAIN_SOURCE.parent/'vision_uart.c').read_bytes()).hexdigest()
    record['uart'] = 'USART1 PA9 TX / PA10 RX, 115200 8N1; R1 J2 UART jumper pairs required'
    record['motor_control'] = 'NOT_IMPLEMENTED'
    p.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
