"""Keep passive voltage queries alive during the fixed single-wheel profile."""
import hashlib,json,shutil
import build_r1_motor_run as previous
import build_r1_drive_bench as helpers
build=previous.build
build.STEM='r1_motor_run_live_voltage';build.WORK=build.TOOLS/'r1-motor-run-live-voltage'
build.OUT=build.PROJECT/'知行回路软件/build/r1_motor_run_live_voltage'
base_prepare=build.PREPARE
def prepare():
 base_prepare();u=build.WORK/'User'
 helpers.edit(u/'motor_probe.c','else if(!motor_pulse_active && (uint32_t)(now-last_query_ms)>=',
              'else if((!motor_pulse_active || motor_speed_mode==4u) && (uint32_t)(now-last_query_ms)>=')
 helpers.edit(u/'remote_drive.c','R1_MOTOR_RUN_20261020','R1_MOTOR_RUN_LIVE_VOLTAGE_20261020')
build.PREPARE=prepare
if __name__=='__main__':
 build.main();snapshot=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snapshot,dirs_exist_ok=True)
 p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
 d.update(date='2026-10-20',scope='Fixed single-wheel350PWM250ms then250PWM,total2200ms; passive voltage queries continue during mode4; timer deadline and voltage/encoder/speed/error guards; P9/P7 DRIVE guarded separately',flash='NOT_RUN',physical_acceptance='NOT_RUN',driver_wire_disconnect_stop='UNRESOLVED',all_source_sha256={x.relative_to(snapshot).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snapshot.rglob('*') if x.suffix in ('.c','.h')})
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(d['binary_sha256'])
