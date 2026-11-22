"""Expose one known bounded start/hold profile, one wheel at a time."""
import hashlib,json,shutil
import build_r1_motor_ready_startup as previous
build=previous.build
build.STEM='r1_motor_run';build.WORK=build.TOOLS/'r1-motor-run'
build.OUT=build.PROJECT/'知行回路软件/build/r1_motor_run'
base_prepare=build.PREPARE
def prepare():
 base_prepare();u=build.WORK/'User';edit=previous.previous.previous.edit
 edit(u/'vision_uart.c','    /* Sensor bench firmware: only STOP accepted from motor command family. */',
 '''    /* Suspended, fixed profile: 350 PWM for250ms then250 PWM, total2200ms. */
    if(!strncmp(line,"BENCH_RUN_M",11)&&line[11]>='1'&&line[11]<='4'&&!line[12]){
        unsigned channel=(unsigned)(line[11]-'0');
        if(motor_startup_hold_start(now,channel,3u)){
            snprintf(response,sizeof(response),"BENCH_RUN_STARTED,M%u\\n",channel);reply(response);
        }else reply("BENCH_RUN_BUSY_OR_OFFLINE\\n");return;
    }
    /* Sensor bench firmware: only STOP accepted from motor command family. */''')
 edit(u/'vision_uart.c','&& strcmp(line,"MOTOR_PULSE_STATUS")',
      '&& strcmp(line,"MOTOR_ENCODER_STATUS") && strcmp(line,"MOTOR_FAULT_STATUS") && strcmp(line,"MOTOR_SPEED_STATUS") && strcmp(line,"MOTOR_PULSE_STATUS")')
 edit(u/'motor_probe.c','    if(!motor_pulse_active||motor_speed_mode)return;',
      '    if(!motor_pulse_active)return;')
 edit(u/'motor_probe.c','(uint32_t)(now-motor_pulse_started_ms)>=250u||',
      '(uint32_t)(now-motor_pulse_started_ms)>=motion_deadline_ms||')
 edit(u/'remote_drive.c','R1_MOTOR_READY_STARTUP_20261020','R1_MOTOR_RUN_20261020')
build.PREPARE=prepare
if __name__=='__main__':
 build.main();snapshot=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snapshot,dirs_exist_ok=True)
 p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
 d.update(date='2026-10-20',scope='Fixed suspended BENCH_RUN_M1..M4: existing350PWM250ms then250PWM, total2200ms; TIM2 deadline/freshness/error/voltage zero; no arbitrary speed/PWM or persistent settings writes; DRIVE range checks retained',flash='NOT_RUN',physical_acceptance='NOT_RUN',driver_wire_disconnect_stop='UNRESOLVED',all_source_sha256={x.relative_to(snapshot).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snapshot.rglob('*') if x.suffix in ('.c','.h')})
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(d['binary_sha256'])
