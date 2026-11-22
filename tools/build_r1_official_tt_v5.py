"""Manufacturer TT speed PID, real profile verification, no assumed PWM duty."""
import hashlib,json,shutil
import build_r1_drive_manual_v4 as previous
build=previous.build;edit=previous.edit
build.STEM='r1_official_tt_v5';build.WORK=build.TOOLS/'r1-official-tt-v5'
build.OUT=build.PROJECT/'知行回路软件/build'/build.STEM
build.EXTRA_SOURCES+=[__import__('pathlib').Path('User/driver_profile.c')]
base_prepare=build.PREPARE
def prepare():
    base_prepare();u=build.WORK/'User';overlay=build.PROJECT/'知行回路软件/board/r1_official_tt'
    for p in overlay.iterdir():shutil.copy2(p,u/p.name)
    p=u/'remote_drive.c'
    edit(p,'R1_DRIVE_STARTUP_MANUAL_V4_20261021','R1_DRIVE_STARTUP_MANUAL_V5_20261021')
    edit(p,'DRIVE_CAPS,2,250,600','DRIVE_CAPS,3,250,600')
    edit(p,'DRIVE_LIMITS,900,600,200,120','DRIVE_LIMITS,3600,0,0,120')
    edit(p,'    /* Explicit manual filming mode: range is advisory, including stale/invalid readings. */',
         '    /* Official TT profile must be read from the real driver each boot. */\n    if(!motor_profile_ready)return 8u;\n    /* Explicit manual filming mode: range is advisory, including stale/invalid readings. */')
    edit(p,'    if(!strcmp(command,"DRIVE_LIMITS"))',
'''    if(!strcmp(command,"DRIVE_PROFILE")){
        snprintf(output,sizeof(output),"DRIVE_PROFILE,%lu,%d,%d,%d,%d,%d,%d,%d,%d\\n",
          (unsigned long)motor_profile_ready,motor_profile.type,motor_profile.deadzone,motor_profile.lines,motor_profile.ratio,
          motor_profile.diameter_milli,motor_profile.p_milli,motor_profile.i_milli,motor_profile.d_milli);reply(output);return 1;
    }
    if(!strcmp(command,"DRIVE_LIMITS"))''')
    p=u/'motor_probe.h';edit(p,'#include <stdint.h>','#include <stdint.h>\n#include "driver_profile.h"\nextern volatile uint32_t motor_profile_ready;\nextern driver_profile_t motor_profile;')
    p=u/'motor_probe.c'
    edit(p,'static char remote_frame[48];','static char remote_frame[48];\nvolatile uint32_t motor_profile_ready;\ndriver_profile_t motor_profile;\nstatic uint8_t profile_boot_silenced,profile_boot_sent;')
    edit(p,'a < -900 || a > 900 || b < -900 || b > 900 || c < -900 || c > 900 || d < -900 || d > 900',
         '!motor_profile_ready || a < -1000 || a > 1000 || b < -1000 || b > 1000 || c < -1000 || c > 1000 || d < -1000 || d > 1000')
    edit(p,'    snprintf(remote_frame,sizeof(remote_frame),"$pwm:%ld,%ld,%ld,%ld#",(long)a,(long)b,(long)c,(long)d);',
'''    if(!a&&!b&&!c&&!d)snprintf(remote_frame,sizeof(remote_frame),"$pwm:0,0,0,0#");
    else snprintf(remote_frame,sizeof(remote_frame),"$spd:%ld,%ld,%ld,%ld#",(long)a,(long)b,(long)c,(long)d);''')
    edit(p,'    motor_parameter_bytes=0;motor_parameter_capture=1;',
         '    motor_parameter_bytes=0;memset((void*)motor_parameter_raw,0,sizeof(motor_parameter_raw));motor_parameter_capture=1;')
    edit(p,'motor_parameter_bytes<sizeof(motor_parameter_raw)','motor_parameter_bytes<sizeof(motor_parameter_raw)-1u')
    edit(p,'''    if(motor_parameter_capture && (uint32_t)(now-parameter_started_ms)>=3000u)
        motor_parameter_capture=0;''',
'''    if(motor_parameter_capture && (uint32_t)(now-parameter_started_ms)>=3000u){
        motor_parameter_capture=0;
        motor_profile_ready=driver_profile_parse((const char*)motor_parameter_raw,&motor_profile);
    }''')
    edit(p,'        else if(!upload_boot_configured){',
'''        else if(!profile_boot_silenced){tx="$upload:0,0,0#";profile_boot_silenced=1;}
        else if(!profile_boot_sent){
            if((uint32_t)(now-last_query_ms)>=100u){
                memset((void*)motor_parameter_raw,0,sizeof(motor_parameter_raw));motor_parameter_bytes=0;
                motor_parameter_capture=1;parameter_started_ms=now;profile_boot_sent=1;tx="$read_flash#";
            }
        }
        else if(motor_parameter_capture){/* Drain the real profile before restoring speed uploads. */}
        else if(!upload_boot_configured){''')
    # Explicit diagnostic reads set capture before publishing parameter_pending.
    # Publish that query first; otherwise the capture wait would swallow it.
    edit(p,'        else if(motor_parameter_capture){/* Drain the real profile before restoring speed uploads. */}',
         '        else if(parameter_pending){tx=parameter_commands[parameter_pending-1u];parameter_pending=0;}\n        else if(motor_parameter_capture){/* Drain the real profile before restoring speed uploads. */}')
    p=u/'vision_uart.c'
    edit(p,'&& strcmp(line,"MOTOR_MONITOR_ON")',
         '&& strcmp(line,"MOTOR_MONITOR_ON") && strcmp(line,"MOTOR_MONITOR_OFF") && strcmp(line,"MOTOR_PARAM_READ") && strcmp(line,"MOTOR_PARAM_STATUS") && strncmp(line,"MOTOR_PARAM_DATA_",17)')
build.PREPARE=prepare
if __name__=='__main__':
    build.main();snap=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snap,dirs_exist_ok=True)
    base=build.PROJECT/'知行回路软件/build/r1_drive_startup_manual_v4/source-snapshot'
    changed=[p.relative_to(snap).as_posix() for p in snap.rglob('*') if p.is_file() and (not (base/p.relative_to(snap)).exists() or p.read_bytes()!=(base/p.relative_to(snap)).read_bytes())]
    assert sorted(changed)==['driver_profile.c','driver_profile.h','motor_probe.c','motor_probe.h','remote_drive.c','vision_uart.c','wheel_control.c'],changed
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
    d.update(date='2026-10-21',scope='Manufacturer encoder TT spd PID; official protocol speed1000/PWM3600 bounds; filming speed cap120; boot read actual TT3/13/45/65mm/defaultPID/deadzone and gate ARM; no assumed actual PWM; PWMzero stop,600ms lease,driver faults,PA0PA1/USB retained',changed_sources=changed,flash='NOT_RUN',physical_acceptance='NOT_RUN',ground_steering='NOT_VERIFIED',all_source_sha256={x.relative_to(snap).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snap.rglob('*') if x.suffix in ('.c','.h')})
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(d['binary_sha256'])
