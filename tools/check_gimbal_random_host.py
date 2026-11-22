"""Production random motion range/slew rate/lease rollover checks, no hardware."""
from pathlib import Path
import json,subprocess
root=Path(__file__).resolve().parents[2]
src=root/'知行回路软件/board/r1_gimbal_continuous'
out=root/'知行回路软件/build/r1_gimbal_continuous/host-check';out.mkdir(parents=True,exist_ok=True)
code=r'''
#include <assert.h>
#include <stdio.h>
#include "gimbal_random.h"
int main(void){
 gimbal_random_t r;uint32_t t;uint16_t y,p;
 random_init(&r,0);
 for(t=1;t<=100000;t++){
  if(t%1000==0)r.last_keepalive_ms=t;
  assert(random_alive(&r,t));y=r.yaw;p=r.pitch;random_step(&r,t);
  assert(difference(y,r.yaw)<=1 && difference(p,r.pitch)<=1);
  assert(r.yaw>=1300 && r.yaw<=1700 && r.pitch>=1350 && r.pitch<=1650);
  assert(r.target_yaw>=1300 && r.target_yaw<=1700 && r.target_pitch>=1350 && r.target_pitch<=1650);
 }
 assert(r.targets>10);
 assert(random_alive(&r,102999));assert(!random_alive(&r,103000));
 random_init(&r,0xffffff00u);
 assert(random_alive(&r,2743));assert(!random_alive(&r,2744));
 r.last_keepalive_ms=3000;assert(random_alive(&r,5999));assert(!random_alive(&r,6000));
 y=r.yaw;p=r.pitch;random_step(&r,100000);
 assert(difference(y,r.yaw)<=1 && difference(p,r.pitch)<=1);
 puts("RANDOM_DUAL_RANGE_SLEW_LEASE_WRAP_PASS");return 0;
}
'''
(out/'check.c').write_text(code,encoding='utf-8')
tcc=root/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe'
subprocess.run([str(tcc),'-I'+str(src),'-o',str(out/'check.exe'),str(out/'check.c')],check=True)
r=subprocess.run([str(out/'check.exe')],check=True,capture_output=True,text=True)
(out/'result.json').write_text(json.dumps({'result':r.stdout.strip(),'hardware_access':'NONE'},indent=2)+'\n',encoding='utf-8')
print(r.stdout.strip())
