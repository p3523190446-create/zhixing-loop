from pathlib import Path
import json,subprocess
root=Path(__file__).resolve().parents[2]
src=root/'知行回路软件/board/r1_gimbal_wide'
out=root/'知行回路软件/build/r1_gimbal_wide/host-check';out.mkdir(parents=True,exist_ok=True)
code=r'''
#include <assert.h>
#include <stdio.h>
#include "gimbal_random.h"
int main(void){
 gimbal_random_t r;uint32_t t;uint16_t y,p;
 assert(manual_target_valid(1000,1000) && manual_target_valid(2000,2000));
 assert(!manual_target_valid(999,1500) && !manual_target_valid(2001,1500));
 assert(!manual_target_valid(1500,999) && !manual_target_valid(1500,2001));
 assert(!manual_target_valid(0xffffffffu,1500));
 random_init(&r,0);r.target_yaw=2000;r.target_pitch=1000;
 for(t=1;t<=10000;t++){
  y=r.yaw;p=r.pitch;manual_step(&r,t);
  assert(difference(y,r.yaw)<=1 && difference(p,r.pitch)<=1);
  assert(manual_target_valid(r.yaw,r.pitch));
 }
 assert(r.yaw==2000 && r.pitch==1000);
 manual_step(&r,1000000);assert(r.yaw==2000 && r.pitch==1000);
 r.target_yaw=1000;r.target_pitch=2000;
 for(t=1000010;t<1011010;t+=10)manual_step(&r,t);
 assert(r.yaw==1000 && r.pitch==2000);
 assert(random_alive(&r,2999) && !random_alive(&r,3000));
 puts("MANUAL_TARGET_CLAMP_SLEW_HOLD_LEASE_PASS");return 0;
}
'''
(out/'check.c').write_text(code,encoding='utf-8')
tcc=root/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe'
subprocess.run([str(tcc),'-I'+str(src),'-o',str(out/'check.exe'),str(out/'check.c')],check=True)
r=subprocess.run([str(out/'check.exe')],check=True,capture_output=True,text=True)
(out/'result.json').write_text(json.dumps({'result':r.stdout.strip(),'hardware_access':'NONE'},indent=2)+'\n',encoding='utf-8')
print(r.stdout.strip())
