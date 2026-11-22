"""Change only the deployed V3 manual-gimbal slew, limits and capability reply."""
from pathlib import Path
import hashlib,json,shutil
import build_r1_mecanum_groundmap as previous
build=previous.build
BASE=build.OUT/'source-snapshot';BASE_WORK=build.WORK
BASE_BINARY=build.OUT/(build.STEM+'.bin')
BASE_SHA='6295f57e98d9d3bd4157a119eb238a446f020732f494e37a7ee66a17c9fa87f2'
assert hashlib.sha256(BASE_BINARY.read_bytes()).hexdigest()==BASE_SHA
build.STEM='r1_gimbal_responsive';build.WORK=build.TOOLS/'r1-gimbal-responsive'
build.OUT=build.PROJECT/'知行回路软件/build'/build.STEM
OVERLAY=build.PROJECT/'知行回路软件/board'/build.STEM
CAPS='GIMBAL_CAPS,2,500,2500,4000'
def prepare():
 OVERLAY.mkdir(exist_ok=True)
 h=(BASE/'gimbal_random.h').read_text(encoding='utf-8')
 h=h.replace('yaw>=1000u && yaw<=2000u && pitch>=1000u && pitch<=2000u','yaw>=500u && yaw<=2500u && pitch>=500u && pitch<=2500u')
 begin=h.index('static inline void manual_step(')
 h=h[:begin]+'''/* Manual mode: up to40us each10ms (4000us/s), no delayed catch-up.
 * Random mode and the independent3000ms watchdog remain unchanged. */
static inline uint16_t manual_toward(uint16_t value,uint16_t target)
{
    if(value<target)return target-value>40?(uint16_t)(value+40u):target;
    if(value>target)return value-target>40?(uint16_t)(value-40u):target;
    return value;
}
static inline void manual_step(gimbal_random_t *r,uint32_t now)
{
    if((uint32_t)(now-r->last_step_ms)<10u)return;
    r->last_step_ms=now;
    r->yaw=manual_toward(r->yaw,r->target_yaw);
    r->pitch=manual_toward(r->pitch,r->target_pitch);
}
#endif
'''
 (OVERLAY/'gimbal_random.h').write_text(h,encoding='utf-8')
 n=(BASE/'native_usb.c').read_text(encoding='utf-8');assert 'GIMBAL_CAPS,1\\n' in n
 (OVERLAY/'native_usb.c').write_text(n.replace('GIMBAL_CAPS,1\\n',CAPS+'\\n'),encoding='utf-8')
 for name in ['ST_API','GuardCore']:shutil.copytree(BASE_WORK/name,build.WORK/name,dirs_exist_ok=True)
 shutil.copytree(BASE,build.WORK/'User',dirs_exist_ok=True)
 for name in ['gimbal_random.h','native_usb.c']:shutil.copy2(OVERLAY/name,build.WORK/'User'/name)
build.PREPARE=prepare
if __name__=='__main__':
 build.main();snap=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snap,dirs_exist_ok=True)
 changed=sorted(x.relative_to(snap).as_posix() for x in snap.rglob('*') if x.is_file() and x.read_bytes()!=(BASE/x.relative_to(snap)).read_bytes())
 assert changed==['gimbal_random.h','native_usb.c'],changed
 p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
 d.update(date="2026-11-07",baseline_binary_sha256=BASE_SHA,changed_sources_vs_deployed=changed,gimbal_caps=CAPS,flash='NOT_RUN',
  all_source_sha256={x.relative_to(snap).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snap.rglob('*') if x.is_file()})
 p.write_text(json.dumps(d,indent=2),encoding='utf-8')
