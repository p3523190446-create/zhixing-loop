"""Exercise actual capture state: timer wrap, no echo, late echo, stale and malformed pulse."""
from pathlib import Path
import subprocess,json
root=Path(__file__).resolve().parents[2]
out=root/'知行回路软件/build/r1_ultrasonic_probe/host-check';out.mkdir(parents=True,exist_ok=True)
src=root/'知行回路软件/board/r1_ultrasonic_probe'
code=r'''
#include <assert.h>
#include <stdio.h>
#include "ultrasonic_state.h"
int main(void){
 ultra_state_t u={0};
 assert(ultra_begin(&u,100,0));ultra_edge(&u,101,65000,1);ultra_edge(&u,102,630,0);
 assert(u.valid && u.distance_mm==200 && u.pulse_us==1166 && u.good_count==1);
 assert(!ultra_begin(&u,199,0));assert(ultra_begin(&u,200,0));
 ultra_expire(&u,234);assert(u.phase);ultra_expire(&u,235);
 assert(!u.valid && u.status==2 && u.timeout_count==1 && u.distance_mm==0xffffffffu);
 ultra_edge(&u,236,900,0);assert(!u.valid && u.good_count==1);
 assert(!ultra_begin(&u,300,1));assert(u.status==3 && !u.valid);
 assert(ultra_begin(&u,400,0));ultra_edge(&u,401,0,0);assert(u.phase==1);
 ultra_edge(&u,402,1000,1);ultra_edge(&u,403,1005,0);assert(u.status==4 && !u.valid);
 assert(ultra_begin(&u,500,0));ultra_edge(&u,501,1000,1);
 ultra_edge(&u,535,2100,0);assert(u.status==2 && !u.valid && u.good_count==1);
 assert(ultra_begin(&u,600,0));ultra_edge(&u,601,1000,1);ultra_edge(&u,603,2166,0);
 ultra_expire(&u,902);assert(u.valid);ultra_expire(&u,903);assert(!u.valid && u.status==5);
 u.phase=0;u.last_trigger_ms=0xffffff00u;
 assert(ultra_begin(&u,0xfffffff0u,0));ultra_expire(&u,0x12u);assert(u.phase);
 ultra_expire(&u,0x13u);assert(!u.phase && u.status==2);
 puts("ULTRASONIC_WRAP_TIMEOUT_STALE_BAD_EDGE_PASS");return 0;
}
'''
(out/'check.c').write_text(code,encoding='utf-8')
tcc=root/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe'
subprocess.run([str(tcc),'-I'+str(src),'-o',str(out/'check.exe'),str(out/'check.c')],check=True)
r=subprocess.run([str(out/'check.exe')],check=True,capture_output=True,text=True)
(out/'result.json').write_text(json.dumps({'result':r.stdout.strip(),'scope':'actual capture state host test; no hardware access'},indent=2)+'\n',encoding='utf-8')
print(r.stdout.strip())
