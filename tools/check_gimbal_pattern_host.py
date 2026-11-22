"""Production dual-axis pattern: isolation, clamp, return-to-center and deadline."""
from pathlib import Path
import json,subprocess
root=Path(__file__).resolve().parents[2]
src=root/'知行回路软件/board/r1_gimbal_probe'
out=root/'知行回路软件/build/r1_gimbal_probe/host-check';out.mkdir(parents=True,exist_ok=True)
code=r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include "servo_probe.h"
int main(void){
 unsigned m;uint32_t t;gimbal_pulses_t p;
 for(m=1;m<=3;m++)for(t=0;t<2500;t++){
  p=gimbal_pattern(t,m);
  if(m==1)assert(p.pitch==0 && p.yaw>=1400 && p.yaw<=1600);
  if(m==2)assert(p.yaw==0 && p.pitch>=1400 && p.pitch<=1600);
  if(m==3)assert(p.yaw>=1400 && p.yaw<=1600 && p.pitch>=1400 && p.pitch<=1600);
 }
 for(m=1;m<=3;m++){
  p=gimbal_pattern(2499,m);assert((m==2 || p.yaw==1500) && (m==1 || p.pitch==1500));
  p=gimbal_pattern(2500,m);assert(!p.yaw && !p.pitch);
  p=gimbal_pattern((uint32_t)(2244u-0xffffff00u),m);assert(!p.yaw && !p.pitch);
 }
 p=gimbal_pattern(500,3);assert(p.yaw==1600 && p.pitch==1400);
 p=gimbal_pattern(1500,3);assert(p.yaw==1400 && p.pitch==1600);
 p=gimbal_pattern(0,0);assert(!p.yaw && !p.pitch);
 p=gimbal_pattern(0,4);assert(!p.yaw && !p.pitch);
 puts("GIMBAL_ISOLATION_BOUNDS_RETURN_TIMEOUT_WRAP_PASS");return 0;
}
'''
(out/'check.c').write_text(code,encoding='utf-8')
tcc=root/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe'
subprocess.run([str(tcc),'-I'+str(src),'-o',str(out/'check.exe'),str(out/'check.c')],check=True)
r=subprocess.run([str(out/'check.exe')],check=True,capture_output=True,text=True)
(out/'result.json').write_text(json.dumps({'result':r.stdout.strip(),'scope':'production pattern host test only; no hardware'},indent=2)+'\n',encoding='utf-8')
print(r.stdout.strip())
