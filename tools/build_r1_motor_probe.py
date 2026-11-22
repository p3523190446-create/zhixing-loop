"""Build USART3 voltage-query diagnostic; never flashes or drives wheels."""
from pathlib import Path
import json,hashlib,shutil
import build_r1_screen_layout as layout
build=layout.build
build.STEM='r1_motor_probe'
build.WORK=build.TOOLS/'r1-motor-probe'
build.OUT=build.PROJECT/'知行回路软件/build/r1_motor_probe'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_motor_probe/main.c'
build.EXTRA_SOURCES += [Path('User/motor_probe.c')]
def prepare():
    layout.prepare()
    for p in build.MAIN_SOURCE.parent.iterdir():
        if p.suffix in ('.c','.h'):shutil.copy2(p,build.WORK/'User'/p.name)
build.PREPARE=prepare
if __name__=='__main__':
    build.main()
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
    d['date']='2026-10-08'
    d['all_source_sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in build.MAIN_SOURCE.parent.iterdir() if x.suffix in ('.c','.h')}
    d['scope']='USART3 PD8/PD9 115200 8N1: boot zero PWM release and read_vol only; no nonzero motion or persistent driver writes'
    p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
