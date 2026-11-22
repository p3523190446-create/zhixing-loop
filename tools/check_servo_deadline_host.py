"""Check production pulse-pattern boundaries and timer wrap; no hardware."""
from pathlib import Path
import json,subprocess
root=Path(__file__).resolve().parents[2]
src=root/'知行回路软件/board/r1_servo_probe'
out=root/'知行回路软件/build/r1_servo_probe/host-check';out.mkdir(parents=True,exist_ok=True)
code=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "servo_probe.h"
int main(void){
 uint32_t elapsed, start=0xffffff00u;
 for(elapsed=0;elapsed<1000;elapsed++){
  assert(servo_probe_pattern(elapsed,0)==1500);
  assert(servo_probe_pattern(elapsed,1)>=1400 && servo_probe_pattern(elapsed,1)<=1600);
 }
 assert(servo_probe_pattern(199,1)==1500 && servo_probe_pattern(200,1)==1400);
 assert(servo_probe_pattern(399,1)==1400 && servo_probe_pattern(400,1)==1500);
 assert(servo_probe_pattern(599,1)==1500 && servo_probe_pattern(600,1)==1600);
 assert(servo_probe_pattern(799,1)==1600 && servo_probe_pattern(800,1)==1500);
 assert(servo_probe_pattern(999,1)==1500 && servo_probe_pattern(1000,1)==0);
 assert(servo_probe_pattern((uint32_t)(744u-start),1)==0);
 assert(servo_probe_pattern(0xffffffffu,0)==0);
 for(elapsed=0;elapsed<2500;elapsed++){
  assert(servo_probe_pattern(elapsed,2)>=1300 && servo_probe_pattern(elapsed,2)<=1700);
 }
 assert(servo_probe_pattern(499,2)==1500 && servo_probe_pattern(500,2)==1300);
 assert(servo_probe_pattern(999,2)==1300 && servo_probe_pattern(1000,2)==1500);
 assert(servo_probe_pattern(1499,2)==1500 && servo_probe_pattern(1500,2)==1700);
 assert(servo_probe_pattern(1999,2)==1700 && servo_probe_pattern(2000,2)==1500);
 assert(servo_probe_pattern(2499,2)==1500 && servo_probe_pattern(2500,2)==0);
 assert(servo_probe_pattern((uint32_t)(2244u-start),2)==0);
 assert(servo_probe_pattern(0,3)==0);
 puts("SERVO_PATTERN_DEADLINE_WRAP_PASS");return 0;
}
'''
(out/'check.c').write_text(code,encoding='utf-8')
tcc=root/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe'
subprocess.run([str(tcc),'-I'+str(src),'-o',str(out/'check.exe'),str(out/'check.c')],check=True)
r=subprocess.run([str(out/'check.exe')],check=True,capture_output=True,text=True)
(out/'result.json').write_text(json.dumps({'result':r.stdout.strip(),'hardware_access':'NONE'},indent=2)+'\n',encoding='utf-8')
print(r.stdout.strip())
