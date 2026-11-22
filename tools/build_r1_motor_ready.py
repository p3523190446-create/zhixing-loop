"""Fixed single-wheel suspended pulse; retain range guards on actual DRIVE."""
from pathlib import Path
import hashlib,json,shutil
import build_r1_drive_bench as previous
build=previous.build
build.STEM='r1_motor_ready';build.WORK=build.TOOLS/'r1-motor-ready'
build.OUT=build.PROJECT/'知行回路软件/build/r1_motor_ready'
base_prepare=build.PREPARE
def prepare():
    base_prepare();u=build.WORK/'User';edit=previous.edit
    edit(u/'vision_uart.c','&& strcmp(line,"MOTOR_MONITOR_ON"))',
         '&& strcmp(line,"MOTOR_MONITOR_ON") && strcmp(line,"MOTOR_PULSE_STATUS") && strncmp(line,"MOTOR_TEST_M",12))')
    p=u/'motor_probe.c';s=p.read_text(encoding='utf8')
    assert s.count('900')==4
    s=s.replace('900','250')
    s=s.replace('    motion_deadline_ms=250u;motor_speed_mode=0;',
        '    if(!motor_speed_frames||(uint32_t)(now-motor_speed_last_ms)>250u)return 0;\n    motion_deadline_ms=250u;motor_speed_mode=0;',1)
    s+='''
/* Fixed short pulse only: TIM2 can revoke without relying on main-loop progress.
 * No obstacle guard here because these commands are explicitly suspended tests.
 * DRIVE continues to enforce its original physical range guard.
 */
void motor_bench_tick(uint32_t now)
{
    if(!motor_pulse_active||motor_speed_mode)return;
    if((uint32_t)(now-motor_pulse_started_ms)>=250u||
       !motor_speed_frames||(uint32_t)(now-motor_speed_last_ms)>250u||
       !motor_encoder_frames||(uint32_t)(now-motor_encoder_last_ms)>250u||
       !motor_voltage_frames||(uint32_t)(now-motor_voltage_last_ms)>1500u||
       motor_voltage_mv<6000u||motor_voltage_mv>8500u||motor_rx_errors||motor_rx_drops)
        motor_remote_stop_now();
}
'''
    p.write_text(s,encoding='utf8')
    with (u/'motor_probe.h').open('a',encoding='utf8') as f:f.write('\nvoid motor_bench_tick(uint32_t now);\n')
    edit(u/'main.c','    remote_drive_tick(now);','    motor_bench_tick(now);\n    remote_drive_tick(now);')
    edit(u/'remote_drive.c','R1_DRIVE_BENCH_20261020','R1_MOTOR_READY_20261020')
build.PREPARE=prepare
if __name__=='__main__':
    build.main()
    snapshot=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snapshot,dirs_exist_ok=True)
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
    d.update(date='2026-10-20',scope='Fixed P9 MOTOR_TEST_M1..M4 PWM250 for250ms; timer-level zero; fresh encoder/speed/voltage and error guards; explicit suspended bench, no range bypass for DRIVE; old variable-speed/parameter commands remain disabled',flash='NOT_RUN',physical_acceptance='NOT_RUN',driver_wire_disconnect_stop='UNRESOLVED',all_source_sha256={x.relative_to(snapshot).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snapshot.rglob('*') if x.suffix in ('.c','.h')})
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(d['binary_sha256'])
