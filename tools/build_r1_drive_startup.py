"""Per-wheel breakaway/feedback controller on verified TIM5/P9-TX baseline."""
from pathlib import Path
import hashlib,json,shutil
import build_r1_gimbal_p9_tx as previous
build=previous.build
build.STEM='r1_drive_startup';build.WORK=build.TOOLS/'r1-drive-startup';build.OUT=build.PROJECT/'知行回路软件/build/r1_drive_startup'
build.EXTRA_SOURCES+=[Path('User/wheel_control.c')]
base_prepare=build.PREPARE
edit=previous.replace
def prepare():
    base_prepare();u=build.WORK/'User';overlay=build.PROJECT/'知行回路软件/board/r1_drive_startup'
    for p in overlay.glob('*'):
        if p.suffix in ('.c','.h'):shutil.copy2(p,u/p.name)
    p=u/'remote_drive.c'
    edit(p,'#include "remote_drive.h"','#include "remote_drive.h"\n#include "wheel_control.h"')
    edit(p,'static volatile int32_t desired_left,desired_right;','static volatile int32_t desired_left,desired_right;\nstatic uint32_t controller_last;')
    edit(p,'    motor_remote_stop_now();\n}', '    wheel_control_stop();motor_remote_stop_now();\n}')
    edit(p,'    if(remote_drive_armed&&dirty&&motor_remote_write(desired_left,desired_right))dirty=0u;',
'''    if(!remote_drive_armed)return;
    if((uint32_t)(now-controller_last)<20u)return;
    controller_last=now;
    if(wheel_control_step(now,desired_left,desired_right,motor_speed_values)){remote_drive_stop(7u);return;}
    if(!remote_drive_armed){wheel_control_stop();return;}
    /* Fresh accepted vectors still expire after600ms. Feedback never renews it. */
    if(motor_remote_write4(wheel_outputs[0],wheel_outputs[1],wheel_outputs[2],wheel_outputs[3]))dirty=0u;''')
    edit(p,'    if(!strcmp(command,"DRIVE_ID"))',
'''    if(!strcmp(command,"DRIVE_ACTUATORS")){
        snprintf(output,sizeof(output),"ACTUATORS,%lu,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%lu\\n",
            (unsigned long)now,(long)wheel_outputs[0],(long)wheel_outputs[1],(long)wheel_outputs[2],(long)wheel_outputs[3],
            (long)wheel_targets[0],(long)wheel_targets[1],(long)wheel_targets[2],(long)wheel_targets[3],(unsigned long)wheel_fault);
        reply(output);return 1;
    }
    if(!strcmp(command,"DRIVE_ID"))''')
    edit(p,'R1_GIMBAL_TIM5_P9_TX_20261021','R1_DRIVE_STARTUP_20261021')
    edit(p,'        motor_remote_stop_now();remote_drive_moving=0;remote_drive_armed=1;',
         '        wheel_control_reset();controller_last=now-20u;motor_remote_stop_now();remote_drive_moving=0;remote_drive_armed=1;')
    edit(p,'if(brake){dirty=0;motor_remote_stop_now();','if(brake){dirty=0;wheel_control_stop();motor_remote_stop_now();')
    p=u/'remote_drive.h';edit(p,'int motor_remote_write(int32_t left,int32_t right);','int motor_remote_write4(int32_t a,int32_t b,int32_t c,int32_t d);')
    p=u/'motor_probe.c'
    edit(p,'int motor_remote_write(int32_t left,int32_t right)','int motor_remote_write4(int32_t a,int32_t b,int32_t c,int32_t d)')
    edit(p,'    if(left < -250 || left > 250 || right < -250 || right > 250)return 0;',
         '    if(!remote_drive_armed || a < -375 || a > 375 || b < -375 || b > 375 || c < -375 || c > 375 || d < -375 || d > 375)return 0;')
    edit(p,'(long)left,(long)left,(long)right,(long)right);','(long)a,(long)b,(long)c,(long)d);')
    # Existing explicitly fixed single-wheel bench is raised only25PWM for comparison.
    edit(p,'    v[channel-1u]=350u;','    v[channel-1u]=375u;')
    edit(p,'tx=calibration_command;motor_speed_mode=4;hold_pending=1;motor_control_pwm=350;',
         'tx=calibration_command;motor_speed_mode=4;hold_pending=1;motor_control_pwm=375;')
    edit(p,'(uint32_t)(now-motor_pulse_started_ms)>=250u','(uint32_t)(now-motor_pulse_started_ms)>=300u')
build.PREPARE=prepare
if __name__=='__main__':
    build.main();snapshot=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snapshot,dirs_exist_ok=True)
    baseline=build.PROJECT/'知行回路软件/build/r1_gimbal_p9_tx/source-snapshot'
    changed=[p.relative_to(snapshot).as_posix() for p in snapshot.rglob('*') if p.is_file() and (not (baseline/p.relative_to(snapshot)).exists() or p.read_bytes()!=(baseline/p.relative_to(snapshot)).read_bytes())]
    assert sorted(changed)==['motor_probe.c','remote_drive.c','remote_drive.h','wheel_control.c','wheel_control.h'],changed
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
    d.update(date='2026-10-21',scope='Suspended per-wheel375PWM300ms startup, raw speed target40..120, bounded PI375PWM,1s no-motion stop,overspeed/reversal guard;600ms fresh-vector lease unchanged; PA0/PA1/USB/P9TX unchanged',changed_sources=changed,flash='NOT_RUN',physical_acceptance='NOT_RUN',all_source_sha256={x.relative_to(snapshot).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snapshot.rglob('*') if x.suffix in ('.c','.h')})
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(d['binary_sha256'])
