"""Build bounded DRIVE protocol on P9 and P7, preserving deployed trace baseline."""
from pathlib import Path
import hashlib,json,shutil
import build_r1_ipad_drive_trace as previous

build=previous.build
build.STEM='r1_drive_bench';build.WORK=build.TOOLS/'r1-drive-bench'
build.OUT=build.PROJECT/'知行回路软件/build/r1_drive_bench'
old_prepare=build.PREPARE

def edit(path,old,new):
    s=path.read_text(encoding='utf8')
    assert s.count(old)==1,(path.name,old)
    path.write_text(s.replace(old,new),encoding='utf8')

def prepare():
    old_prepare()
    u=build.WORK/'User'
    edit(u/'vision_uart.c','#include "motor_probe.h"','#include "motor_probe.h"\n#include "remote_drive.h"')
    edit(u/'vision_uart.c','if(uvc_bridge_command(line,now,reply))return;',
         'if(remote_drive_uart_command(line,now,reply))return;\n    if(uvc_bridge_command(line,now,reply))return;')
    edit(u/'vision_uart.c','&& strcmp(line,"MOTOR_STATUS"))',
         '&& strcmp(line,"MOTOR_STATUS") && strcmp(line,"MOTOR_RAW") && strcmp(line,"MOTOR_MONITOR_ON"))')
    # An explicitly requested monitor refresh sends no nonzero PWM or flash settings.
    # Keep all legacy nonzero/parameter commands disabled.
    edit(u/'remote_drive.c','static volatile int32_t desired_left,desired_right;',
         'static volatile int32_t desired_left,desired_right;\nvolatile uint32_t remote_drive_uart_owner;\nstatic volatile uint32_t seen_errors,seen_drops,error_changed_ms;')
    edit(u/'remote_drive.c','    remote_drive_armed=remote_drive_moving=0u;',
         '    remote_drive_armed=remote_drive_moving=remote_drive_uart_owner=0u;')
    edit(u/'remote_drive.c','int remote_drive_command(const char *command,uint32_t now,void (*reply)(const char *))',
         'static int remote_drive_common(const char *command,uint32_t now,void (*reply)(const char *))')
    with (u/'remote_drive.c').open('a',encoding='utf8') as f:
        f.write('''
int remote_drive_command(const char *c,uint32_t n,void (*r)(const char *))
{if(!strcmp(c,"DRIVE_ARM")&&!remote_drive_armed)remote_drive_uart_owner=0;return remote_drive_common(c,n,r);}
int remote_drive_uart_command(const char *c,uint32_t n,void (*r)(const char *))
{if(!strcmp(c,"DRIVE_ARM")&&!remote_drive_armed)remote_drive_uart_owner=1;return remote_drive_common(c,n,r);}
''')
    with (u/'remote_drive.h').open('a',encoding='utf8') as f:
        f.write('\nextern volatile uint32_t remote_drive_uart_owner;\nint remote_drive_uart_command(const char *,uint32_t,void (*)(const char *));\n')
    # USB loss revokes USB-owned driving. P9 has the same independent 600ms
    # fresh-vector lease and physical guards; an absent P7 is not its transport.
    p=u/'native_usb.c';s=p.read_text(encoding='utf8')
    assert s.count('if(remote_drive_armed){remote_drive_stop(3u);}')==2
    s=s.replace('if(remote_drive_armed){remote_drive_stop(3u);}',
                'if(remote_drive_armed&&!remote_drive_uart_owner){remote_drive_stop(3u);}')
    s=s.replace('        servo_probe_stop();if(camera_link_active){uvc_bridge_stop();camera_link_active=0;}',
                '        if(camera_link_active){servo_probe_stop();uvc_bridge_stop();camera_link_active=0;}')
    p.write_text(s,encoding='utf8')
    edit(u/'remote_drive.c','    if(!motor_voltage_frames||',
         '    if(motor_rx_errors!=seen_errors||motor_rx_drops!=seen_drops||\n       (uint32_t)(now-error_changed_ms)<1500u)return 4u;\n    if(motor_voltage_mv<6000u||motor_voltage_mv>8500u)return 4u;\n    if(!motor_voltage_frames||')
    edit(u/'remote_drive.c','motor_rx_errors||motor_rx_drops||motor_speed_fault','motor_speed_fault')
    edit(u/'remote_drive.c','    if(!remote_drive_armed)return;',
         '''    if(motor_rx_errors!=seen_errors||motor_rx_drops!=seen_drops){
        seen_errors=motor_rx_errors;seen_drops=motor_rx_drops;error_changed_ms=now;
        if(remote_drive_armed){remote_drive_stop(4u);return;}
    }
    if(!remote_drive_armed)return;''')
    edit(u/'remote_drive.c','    if(!strcmp(command,"DRIVE_CAPS"))',
         '''    if(!strcmp(command,"DRIVE_DIAG")){
        snprintf(output,sizeof(output),"DRIVEDIAG,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu\\n",
          (unsigned long)now,(unsigned long)blocked(now),(unsigned long)range_corrected_mm,
          (unsigned long)warning_mm,(unsigned long)(now-led_last_good_ms),
          (unsigned long)motor_voltage_mv,(unsigned long)(now-motor_voltage_last_ms),
          (unsigned long)motor_speed_frames,(unsigned long)(now-motor_speed_last_ms),
          (unsigned long)motor_rx_errors,(unsigned long)motor_rx_drops,
          (unsigned long)(now-error_changed_ms),(unsigned long)motor_speed_fault);reply(output);return 1;
    }
    if(!strcmp(command,"DRIVE_ID")){reply("DRIVE_ID,R1_DRIVE_BENCH_20261020,1\\n");return 1;}
    if(!strcmp(command,"DRIVE_CAPS"))''')

build.PREPARE=prepare
if __name__=='__main__':
    build.main()
    snapshot=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snapshot,dirs_exist_ok=True)
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
    d.update(date='2026-10-20',scope='Suspended bench; same guarded DRIVE protocol P9/P7; 600ms command lease; live range and speed feedback required; 6-8.5V; new UART error revokes immediately and requires explicit rearm after1500ms quiet; read-only diagnostic and explicit passive monitor refresh',flash='NOT_RUN',physical_acceptance='NOT_RUN',ground_drive='NOT_VERIFIED',driver_wire_disconnect_stop='KNOWN_UNRESOLVED',all_source_sha256={x.relative_to(snapshot).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snapshot.rglob('*') if x.suffix in ('.c','.h')})
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(d['binary_sha256'])
