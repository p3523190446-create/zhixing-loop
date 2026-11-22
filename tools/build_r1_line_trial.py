"""User-requested ordinary-wheel low-speed trial; not ground acceptance."""
from pathlib import Path
import json,shutil,hashlib
import build_r1_line_task as normal
build=normal.build;original_prepare=build.PREPARE
build.STEM='r1_line_trial';build.WORK=build.TOOLS/'r1-line-trial';build.OUT=build.PROJECT/'知行回路软件/build/r1_line_trial'
def prepare():
 original_prepare();p=build.WORK/'User/line_task_runtime.c';s=p.read_text(encoding='utf-8')
 assert s.count('#define LINE_TASK_GROUND_READY 0')==s.count('#define LINE_TASK_LOW_SPEED_TRIAL 0')==1
 s=s.replace('#define LINE_TASK_GROUND_READY 0','#define LINE_TASK_GROUND_READY 1').replace('#define LINE_TASK_LOW_SPEED_TRIAL 0','#define LINE_TASK_LOW_SPEED_TRIAL 1');p.write_text(s,encoding='utf-8')
build.PREPARE=prepare
if __name__=='__main__':
 build.main();snap=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snap,dirs_exist_ok=True)
 p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'));d.update(date='2026-11-06',scope='ordinary wheels explicit low-speed trial, 40 speed, max5s, junction stop',ground_permission='LOW_SPEED_TRIAL_ONLY',physical_acceptance='NOT_RUN',flash='NOT_RUN',auto_start=False,limits=dict(speed=40,max_ms=5000,branch=0),all_source_sha256={x.relative_to(snap).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snap.rglob('*') if x.is_file()});p.write_text(json.dumps(d,indent=2),encoding='utf-8')
