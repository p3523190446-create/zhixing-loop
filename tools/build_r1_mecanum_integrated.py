"""Merge mecanum execution into the exact continuous-line source; never flashes."""
from pathlib import Path
import hashlib,json,shutil
import build_r1_line_continuous as previous
from prepare_mecanum import replace
build=previous.build
BASE=build.PROJECT/'知行回路软件/build/r1_line_continuous/source-snapshot'
BASE_WORK=build.WORK
OVERLAY=build.PROJECT/'知行回路软件/board/r1_mecanum_integrated'
OLD=build.PROJECT/'知行回路软件/board/r1_mecanum'
build.STEM='r1_mecanum_integrated';build.WORK=build.TOOLS/'r1-mecanum-integrated'
build.OUT=build.PROJECT/'知行回路软件/build/r1_mecanum_integrated'
build.EXTRA_SOURCES += [Path('User/mecanum_mix.c')]
IDENTITY='R1_DRIVE_STARTUP_MANUAL_MECANUM_V2_20261107'

def overlay():
 OVERLAY.mkdir(exist_ok=True)
 for name in ('wheel_control.c','wheel_control.h','mecanum_mix.c','mecanum_mix.h'):
  shutil.copy2(OLD/name,OVERLAY/name)
 s=(BASE/'remote_drive.c').read_text(encoding='utf-8')
 s=replace(s,'#include "wheel_control.h"','#include "wheel_control.h"\n#include "mecanum_mix.h"')
 s=replace(s,'static volatile int32_t desired_left,desired_right;', 'static volatile int32_t desired_left,desired_right;\nstatic int32_t desired_wheels[4],desired_forward,desired_strafe,desired_turn;')
 s=replace(s,'    desired_left=desired_right=0;dirty=0u;reason=why;', '    desired_left=desired_right=desired_forward=desired_strafe=desired_turn=0;\n    memset(desired_wheels,0,sizeof(desired_wheels));dirty=0u;reason=why;')
 s=replace(s,'wheel_control_step(now,desired_left,desired_right,motor_speed_values)','wheel_control_step4(now,desired_wheels,motor_speed_values)')
 s=replace(s,'R1_DRIVE_STARTUP_MANUAL_V8_20261023',IDENTITY)
 s=replace(s,'DRIVE_CAPS,4,250,600','DRIVE_CAPS,5,250,600')
 s=replace(s,'    if(!strcmp(command,"DRIVE_STATUS")){','''    if(!strcmp(command,"DRIVE_CHASSIS")){reply("DRIVE_CHASSIS,MECANUM_X,FL_RL_FR_RR,250,600\\n");return 1;}
    if(!strcmp(command,"DRIVE_VECTOR_STATUS")){
        snprintf(output,sizeof(output),"DRIVE_VECTOR,%ld,%ld,%ld,%ld,%ld,%ld,%ld\\n",
          (long)desired_forward,(long)desired_strafe,(long)desired_turn,
          (long)desired_wheels[0],(long)desired_wheels[1],(long)desired_wheels[2],(long)desired_wheels[3]);reply(output);return 1;
    }
    if(!strcmp(command,"DRIVE_STATUS")){''')
 s=replace(s,'        desired_left=desired_right=0;dirty=0;reason=0;sequence=0;last_set=now;', '        desired_left=desired_right=desired_forward=desired_strafe=desired_turn=0;memset(desired_wheels,0,sizeof(desired_wheels));\n        dirty=0;reason=0;sequence=0;last_set=now;')
 s=replace(s,'    if(!strncmp(command,"DRIVE_SET,",10)||!strncmp(command,"DRIVE_BRAKE,",12)){','''    if(!strncmp(command,"DRIVE_VECTOR,",13)){
        int32_t f,x,r,targets[4];cursor=command+13;
        if(!unsigned_number(&cursor,&gen,',')||!unsigned_number(&cursor,&seq,',')||
           !pwm_number(&cursor,&f,',')||!pwm_number(&cursor,&x,',')||!pwm_number(&cursor,&r,0))goto invalid;
        if(!remote_drive_armed||gen!=generation||seq<=sequence||!seq)goto invalid;
        why=blocked(now);if(why){remote_drive_stop(why);goto invalid;}
        if(!mecanum_mix(f,x,r,targets))goto invalid;
        sequence=seq;desired_forward=f;desired_strafe=x;desired_turn=r;
        memcpy(desired_wheels,targets,sizeof(targets));desired_left=targets[0];desired_right=targets[2];
        last_set=now;reason=0;remote_drive_moving=f!=0||x!=0||r!=0;dirty=1;
        reply("DRIVE_VECTOR_ACCEPTED\\n");return 1;
    }
    /* Preserve the deployed line task's two-side interface: strafe is zero. */
    if(!strncmp(command,"DRIVE_SET,",10)||!strncmp(command,"DRIVE_BRAKE,",12)){''')
 s=replace(s,'        sequence=seq;desired_left=left;desired_right=right;last_set=now;reason=0;', '        sequence=seq;desired_left=left;desired_right=right;\n        desired_wheels[0]=desired_wheels[1]=left;desired_wheels[2]=desired_wheels[3]=right;\n        desired_forward=(left+right)/2;desired_strafe=0;desired_turn=(left-right)/2;\n        last_set=now;reason=0;')
 assert s.count('!strncmp(c,"DRIVE_SET,",10)')==2
 s=s.replace('!strncmp(c,"DRIVE_SET,",10)','!strncmp(c,"DRIVE_SET,",10)||!strncmp(c,"DRIVE_VECTOR,",13)')
 (OVERLAY/'remote_drive.c').write_text(s,encoding='utf-8')

def prepare():
 overlay()
 for name in ('ST_API','GuardCore'):shutil.copytree(BASE_WORK/name,build.WORK/name,dirs_exist_ok=True)
 shutil.copytree(BASE,build.WORK/'User',dirs_exist_ok=True)
 for p in OVERLAY.iterdir():
  if p.suffix in ('.c','.h'):shutil.copy2(p,build.WORK/'User'/p.name)
build.PREPARE=prepare
if __name__=='__main__':
 build.main();snap=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snap,dirs_exist_ok=True)
 changed=sorted(p.relative_to(snap).as_posix() for p in snap.rglob('*') if p.is_file() and (not (BASE/p.relative_to(snap)).exists() or p.read_bytes()!=(BASE/p.relative_to(snap)).read_bytes()))
 assert changed==['mecanum_mix.c','mecanum_mix.h','remote_drive.c','wheel_control.c','wheel_control.h'],changed
 p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
 d.update(date='2026-11-07',identity=IDENTITY,scope='Mecanum plus unchanged current continuous line/calibration/sensor runtime',changed_sources_vs_continuous=changed,flash='NOT_RUN',physical_acceptance='NOT_RUN',
  baseline_binary_sha256=hashlib.sha256((BASE.parent/'r1_line_continuous.bin').read_bytes()).hexdigest(),all_source_sha256={x.relative_to(snap).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snap.rglob('*') if x.is_file()})
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
