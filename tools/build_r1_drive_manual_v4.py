"""Ground-load candidate: driver PWM900 bound,600/200ms start, speed unchanged."""
import hashlib,json,shutil
import build_r1_drive_manual_v3 as previous
build=previous.build;edit=previous.edit
build.STEM='r1_drive_startup_manual_v4';build.WORK=build.TOOLS/'r1-drive-startup-manual-v4'
build.OUT=build.PROJECT/'知行回路软件/build'/build.STEM
base_prepare=build.PREPARE
def prepare():
    base_prepare();u=build.WORK/'User';p=u/'wheel_control.c'
    edit(u/'remote_drive.c','R1_DRIVE_STARTUP_MANUAL_V3_20261021','R1_DRIVE_STARTUP_MANUAL_V4_20261021')
    edit(u/'remote_drive.c','    if(!strcmp(command,"DRIVE_MODE"))',
         '    if(!strcmp(command,"DRIVE_LIMITS")){reply("DRIVE_LIMITS,900,600,200,120\\n");return 1;}\n    if(!strcmp(command,"DRIVE_MODE"))')
    edit(p,'#define KICK_PWM 375\n#define KICK_MS 300u','#define KICK_PWM 600\n#define MAX_PWM 900\n#define KICK_MS 200u')
    edit(p,'        if(!sign){memset(w,0,sizeof(*w));wheel_outputs[i]=wheel_targets[i]=0;continue;}',
         '        /* Inner requests below60 raw cannot be maintained in prior ground logs.\n         * Explicit coast pivot rather than command an unachievable crawl then stall. */\n        if(wanted<60){sign=0;}\n        if(!sign){memset(w,0,sizeof(*w));wheel_outputs[i]=wheel_targets[i]=0;continue;}')
    edit(p,'wheel_outputs[i]=sign*(KICK_PWM*absolute(input)/peak);continue;',
         'wheel_outputs[i]=sign*KICK_PWM;continue;')
    edit(p,'''            if(absolute(speed)>8){if((uint32_t)(now-w->brake)>800u)return fault(48u+i+1u);continue;}
            if(w->sign && (uint32_t)(now-w->brake)<150u)continue;''',
'''            /* A coasting inner wheel can already roll with the car. Join same
             * direction without waiting for an impossible ground stop. Reversal
             * still requires measured standstill and150ms braking. */
            if(w->sign || sign*speed < -8){
                if(absolute(speed)>8){if((uint32_t)(now-w->brake)>800u)return fault(48u+i+1u);continue;}
                if(w->sign && (uint32_t)(now-w->brake)<150u)continue;
            }''')
    edit(p,'''        w->phase=2;w->last=now;error=wanted-aligned;
        w->integral=bound(w->integral+error*20,-160*256,160*256);
        ff=friction[i]+(feed120[i]-friction[i])*wanted/120;
        pwm=bound(ff+error/3+w->integral/256,0,KICK_PWM);''',
'''        error=wanted-aligned;
        ff=friction[i]+(feed120[i]-friction[i])*wanted/120;
        /* Preserve required loaded torque at startup handover instead of dropping
         * immediately to an unloaded feedforward. Overspeed hands over at zero I. */
        if(w->phase==1)w->integral=aligned<=wanted+10?bound(KICK_PWM-ff-error/3,0,640)*256:0;
        w->phase=2;w->last=now;
        w->integral=bound(w->integral+error*80,-640*256,640*256);
        pwm=bound(ff+error/3+w->integral/256,0,MAX_PWM);''')
    edit(u/'motor_probe.c','a < -375 || a > 375 || b < -375 || b > 375 || c < -375 || c > 375 || d < -375 || d > 375',
         'a < -900 || a > 900 || b < -900 || b > 900 || c < -900 || c > 900 || d < -900 || d > 900')
build.PREPARE=prepare
if __name__=='__main__':
    build.main();snapshot=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snapshot,dirs_exist_ok=True)
    baseline=build.PROJECT/'知行回路软件/build/r1_drive_startup_manual_v3/source-snapshot'
    changed=[p.relative_to(snapshot).as_posix() for p in snapshot.rglob('*') if p.is_file() and (not (baseline/p.relative_to(snapshot)).exists() or p.read_bytes()!=(baseline/p.relative_to(snapshot)).read_bytes())]
    assert sorted(changed)==['motor_probe.c','remote_drive.c','wheel_control.c'],changed
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
    d.update(date='2026-10-21',scope='Ground-load candidate: protocol range3600, bound900;600PWM200ms startup and loaded PI handover; same max raw120 speed,600ms lease/range advisory/driver faults/PA0 PA1/USB; inner raw<60 coast instead of impossible crawl',changed_sources=changed,flash='NOT_RUN',physical_acceptance='NOT_RUN',ground_steering='NOT_VERIFIED',driver_wire_disconnect_stop='KNOWN_UNRESOLVED',all_source_sha256={x.relative_to(snapshot).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snapshot.rglob('*') if x.suffix in ('.c','.h')})
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(d['binary_sha256'])
