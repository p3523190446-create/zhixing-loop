"""Restore this car's verified ID72 sensor sampling at boot; no PC command."""
from pathlib import Path
import hashlib,json,shutil
import build_r1_gimbal_responsive as previous
build=previous.build;BASE=build.OUT/'source-snapshot';BASE_WORK=build.WORK
BASE_BINARY=build.OUT/(build.STEM+'.bin');BASE_SHA='9d78995b91012d6a2f46653283d61fb040f908051c653d9dae0d4b525af13c3b'
assert hashlib.sha256(BASE_BINARY.read_bytes()).hexdigest()==BASE_SHA
build.STEM='r1_phone_standalone';build.WORK=build.TOOLS/'r1-phone-standalone';build.OUT=build.PROJECT/'知行回路软件/build'/build.STEM
OVERLAY=build.PROJECT/'知行回路软件/board'/build.STEM
POLICY='''#ifndef IMU_IDENTITY_POLICY_H
#define IMU_IDENTITY_POLICY_H
#include <stdint.h>
/* The installed0x69 device reports0x72 and uses the saved ID72 reference.
 * Accepted by this car's integration; this does not identify it as genuine MPU6050. */
#define IMU_AUTO_COMPAT_ID72 1u
static inline int imu_identity_allowed(uint8_t id,uint8_t allow72)
{return id==0x68u||(id==0x72u&&allow72);}
#endif
'''
def prepare():
 OVERLAY.mkdir(exist_ok=True);(OVERLAY/'imu_identity_policy.h').write_text(POLICY,encoding='utf-8')
 s=(BASE/'mpu6050_probe.c').read_text(encoding='utf-8').replace('#include "imu_reference.h"','#include "imu_reference.h"\n#include "imu_identity_policy.h"')
 s=s.replace('static uint8_t bus_error,ready,identity,last_error,compat_trial;','static uint8_t bus_error,ready,identity,last_error;\nstatic uint8_t compat_trial=IMU_AUTO_COMPAT_ID72;')
 s=s.replace('/* Unknown 0x72 is never silently classified as a genuine MPU6050.\n     * A deliberate volatile P9-only trial can check register compatibility. */','/* Restore this installed sensor on every boot; all other IDs remain rejected. */')
 s=s.replace('identity!=0x68 && !(identity==0x72 && compat_trial)','!imu_identity_allowed(identity,compat_trial)')
 (OVERLAY/'mpu6050_probe.c').write_text(s,encoding='utf-8')
 for name in ['ST_API','GuardCore']:shutil.copytree(BASE_WORK/name,build.WORK/name,dirs_exist_ok=True)
 shutil.copytree(BASE,build.WORK/'User',dirs_exist_ok=True)
 for name in ['imu_identity_policy.h','mpu6050_probe.c']:shutil.copy2(OVERLAY/name,build.WORK/'User'/name)
build.PREPARE=prepare
if __name__=='__main__':
 build.main();snap=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snap,dirs_exist_ok=True)
 changed=sorted(x.relative_to(snap).as_posix() for x in snap.rglob('*') if x.is_file() and (not (BASE/x.relative_to(snap)).exists() or x.read_bytes()!=(BASE/x.relative_to(snap)).read_bytes()))
 assert changed==['imu_identity_policy.h','mpu6050_probe.c'],changed
 p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
 d.update(date='2026-11-07',baseline_binary_sha256=BASE_SHA,changed_sources_vs_deployed=changed,flash='NOT_RUN',
 all_source_sha256={x.relative_to(snap).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snap.rglob('*') if x.is_file()})
 p.write_text(json.dumps(d,indent=2),encoding='utf-8')
