"""Continuous passive IMU processing over the exact deployed MPU diagnostic app."""
from pathlib import Path
import hashlib,json,shutil,zlib
import build_r1_mpu6050 as previous
build=previous.build
build.STEM='r1_imu_observer';build.WORK=build.TOOLS/'r1-imu-observer'
build.OUT=build.PROJECT/'知行回路软件/build'/build.STEM
OVERLAY=build.PROJECT/'知行回路软件/board/r1_mpu_observer'
BASE=build.PROJECT/'知行回路软件/build/r1_mpu6050_diag/source-snapshot'
REF=build.PROJECT/'output/onboard_dashboard/mpu6050-20261025'
base_prepare=build.PREPARE
build.EXTRA_SOURCES += [Path('User/imu_observer.c')]
original_run=build.run
def run(args):
    if '-nostartfiles' in args:
        i=args.index('-o');args=[*args[:i],'-lm',*args[i:]]
    return original_run(args)
build.run=run
def prepare_reference():
    rb=(REF/'flat-reference.json').read_bytes();mb=(REF/'body-axis-mapping.json').read_bytes()
    ref=json.loads(rb.decode('utf-8'));mapping=json.loads(mb.decode('utf-8'))
    assert ref['who_am_i_hex']==mapping['who_am_i_hex']=='0x72'
    norm=sum(x*x for x in ref['gravity_reference_raw'])**.5
    assert norm>1000 and len(ref['gyro_bias_raw'])==3
    def number(x):return f'{float(x):.9f}f'
    tag=zlib.crc32(rb+mb)&0xffffffff
    header='''/* Generated from user-confirmed level reference and observed axes. */
#ifndef IMU_REFERENCE_H
#define IMU_REFERENCE_H
#include <stdint.h>
'''
    header+=f'#define IMU_REFERENCE_TAG UINT32_C({tag})\n#define IMU_GRAVITY_RAW {number(norm)}\n'
    header+=f'#define IMU_ROLL_REF {number(ref["roll_reference_deg"])}\n#define IMU_PITCH_REF {number(ref["pitch_reference_deg"])}\n'
    header+=f'#define IMU_FRONT_SIGN {number(mapping["front_up_sign"])}\n#define IMU_LEFT_SIGN {number(mapping["left_up_sign"])}\n'
    header+='static const float IMU_GYRO_BIAS[3]={'+','.join(map(number,ref['gyro_bias_raw']))+'};\n#endif\n'
    (OVERLAY/'imu_reference.h').write_text(header,encoding='utf-8');return tag
def prepare():
    base_prepare();u=build.WORK/'User';prepare_reference()
    for p in OVERLAY.iterdir():
        if p.suffix in ('.c','.h'):shutil.copy2(p,u/p.name)
    edit=previous.edit;p=u/'mpu6050_probe.c'
    edit(p,'#include "mpu6050_probe.h"','#include "mpu6050_probe.h"\n#include "imu_observer.h"\n#include "imu_reference.h"')
    edit(p,'static int16_t raw[7];','static imu_observer_t observer;\nstatic long milli(float x){return (long)(x*1000+(x>=0?.5f:-.5f));}\nstatic int16_t raw[7];')
    edit(p,'write_reg(0x1A,0x03)','write_reg(0x1A,0x06)');edit(p,'config[0]!=3','config[0]!=6')
    edit(p,'    last_attempt=now;\n}', '    last_attempt=now;imu_observer_init(&observer);\n}')
    edit(p,'last_sample=now;++samples;last_error=0;return;',
         'last_sample=now;++samples;last_error=0;imu_observer_update(&observer,raw,now);return;')
    edit(p,'char text[192];','char text[256];')
    extra='''    if(!strcmp(command,"MPU_FEATURES_ID"))reply("MPU_FEATURES_ID,IMU_OBSERVER_V1_20HZ\\n");
    else if(!strcmp(command,"MPU_FEATURES")){
        uint32_t a=observer.initialized?(uint32_t)(now-observer.now):0xFFFFFFFFu;
        snprintf(text,sizeof(text),"MPU_FEATURES,%lu,%lu,%u,%lu,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%lu,%lu,%lu,%lu,%lu,%lu\\n",
          (unsigned long)now,(unsigned long)a,(unsigned)(valid&&imu_observer_valid(&observer,now)),(unsigned long)observer.flags,
          milli(observer.front_up),milli(observer.left_up),milli(observer.yaw_window),milli(observer.gyro_z),
          milli(observer.rms),milli(observer.peak),milli(observer.jerk),(unsigned long)observer.shock_count,
          (unsigned long)observer.tilt_count,(unsigned long)observer.fall_count,(unsigned long)observer.window_ms,
          (unsigned long)observer.count,(unsigned long)IMU_REFERENCE_TAG);reply(text);
    }
    else if(!strcmp(command,"MPU_ID"))'''
    edit(p,'    if(!strcmp(command,"MPU_ID"))',extra)
    edit(u/'vision_uart.c','"MPU_ID","MPU_STATUS","MPU_RAW","MPU_DIAG",',
         '"MPU_FEATURES_ID","MPU_FEATURES",\n        "MPU_ID","MPU_STATUS","MPU_RAW","MPU_DIAG",')
build.PREPARE=prepare
if __name__=='__main__':
    build.main();snap=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snap,dirs_exist_ok=True)
    changed=[p.relative_to(snap).as_posix() for p in snap.rglob('*') if p.is_file() and
        (not (BASE/p.relative_to(snap)).exists() or p.read_bytes()!=(BASE/p.relative_to(snap)).read_bytes())]
    assert sorted(changed)==['imu_observer.c','imu_observer.h','imu_reference.h','mpu6050_probe.c','vision_uart.c'],changed
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
    d.update(date='2026-10-25',scope='20Hz passive complementary attitude/2s turn/vibration/events/health; DLPF6, no actuators',
        changed_sources_vs_mpu_diag=changed,reference_crc32=prepare_reference(),identity_warning='0x72 explicit volatile trial only',
        all_source_sha256={p.relative_to(snap).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in snap.rglob('*') if p.is_file()},
        physical_algorithms='NOT_RUN',flash='NOT_RUN')
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
