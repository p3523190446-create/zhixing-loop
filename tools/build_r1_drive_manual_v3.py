"""Manual filming: advisory range and ratio-preserving differential steering."""
import hashlib,json,shutil
import build_r1_drive_startup_stable_v2 as previous
build=previous.build
build.STEM='r1_drive_startup_manual_v3'
build.WORK=build.TOOLS/'r1-drive-startup-manual-v3'
build.OUT=build.PROJECT/'知行回路软件/build'/build.STEM
base_prepare=build.PREPARE
edit=previous.previous.previous.edit

def prepare():
    base_prepare();u=build.WORK/'User'
    edit(u/'remote_drive.c','R1_DRIVE_STARTUP_STABLE_V2_20261021','R1_DRIVE_STARTUP_MANUAL_V3_20261021')
    edit(u/'remote_drive.c','    if(!range_correction_valid||(uint32_t)(now-led_last_good_ms)>=300u||range_corrected_mm<=warning_mm)return 2u;',
         '    /* Explicit manual filming mode: range is advisory, including stale/invalid readings. */')
    edit(u/'remote_drive.c','    if(!strcmp(command,"DRIVE_CAPS"))',
         '    if(!strcmp(command,"DRIVE_MODE")){reply("DRIVE_MODE,MANUAL,1,0\\n");return 1;}\n    if(!strcmp(command,"DRIVE_CAPS"))')
    edit(u/'remote_drive.c','/* Suspension/bench only. These are command amplitudes, not measured mm/s.',
         '/* User-operated manual filming. These are command amplitudes, not measured mm/s.')
    edit(u/'wheel_control.c','/* Suspended bench only. Raw driver speed units, not calibrated vehicle cm/s.',
         '/* Manual differential drive. Raw driver units, not calibrated vehicle cm/s.')
    edit(u/'wheel_control.c','    unsigned i;\n    if(wheel_fault)return wheel_fault;',
         '    unsigned i;\n    int32_t peak=absolute(left)>absolute(right)?absolute(left):absolute(right);\n    int32_t outer=80+peak*40/250;\n    if(wheel_fault)return wheel_fault;')
    edit(u/'wheel_control.c','int32_t wanted=80+absolute(input)*40/250,aligned,error,ff,pwm;',
         'int32_t wanted=peak?(outer*absolute(input)+peak/2)/peak:0,aligned,error,ff,pwm;')
    edit(u/'wheel_control.c','wanted=bound(wanted,80,120);','wanted=bound(wanted,1,120);')
    edit(u/'wheel_control.c','wheel_outputs[i]=sign*KICK_PWM;continue;',
         'wheel_outputs[i]=sign*(KICK_PWM*absolute(input)/peak);continue;')
    edit(u/'motor_probe.c',' * DRIVE continues to enforce its original physical range guard.',
         ' * Manual DRIVE keeps driver/lease guards; range is advisory.')
build.PREPARE=prepare
if __name__=='__main__':
    build.main();snapshot=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snapshot,dirs_exist_ok=True)
    baseline=build.PROJECT/'知行回路软件/build/r1_drive_startup_stable_v2/source-snapshot'
    changed=[p.relative_to(snapshot).as_posix() for p in snapshot.rglob('*') if p.is_file() and (not (baseline/p.relative_to(snapshot)).exists() or p.read_bytes()!=(baseline/p.relative_to(snapshot)).read_bytes())]
    assert sorted(changed)==['motor_probe.c','remote_drive.c','wheel_control.c'],changed
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
    d.update(date='2026-10-21',scope='Explicit manual filming: range advisory; proportional inner/outer target and startup; unchanged375PWM300ms bound/600ms lease/driver faults/PA0 PA1/USB',changed_sources=changed,flash='NOT_RUN',physical_acceptance='NOT_RUN',ground_steering='NOT_VERIFIED',driver_wire_disconnect_stop='KNOWN_UNRESOLVED',all_source_sha256={x.relative_to(snapshot).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snapshot.rglob('*') if x.suffix in ('.c','.h')})
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(d['binary_sha256'])
