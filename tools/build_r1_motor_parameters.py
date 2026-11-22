import json,hashlib
import build_r1_motor_probe as probe
build=probe.build
build.STEM='r1_motor_parameters'
build.WORK=build.TOOLS/'r1-motor-parameters'
build.OUT=build.PROJECT/'知行回路软件/build/r1_motor_parameters'
build.MAIN_SOURCE=build.PROJECT/'知行回路软件/board/r1_motor_parameters/main.c'
if __name__=='__main__':
    build.main()
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
    d['date']='2026-10-08'
    d['all_source_sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in build.MAIN_SOURCE.parent.iterdir() if x.suffix in ('.c','.h')}
    d['scope']='Read-only read_flash driver parameter query; preserves verified encoder and bench pulse commands'
    p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
