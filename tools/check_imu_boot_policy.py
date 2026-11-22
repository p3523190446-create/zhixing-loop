from pathlib import Path
import json,subprocess
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'知行回路软件/build/r1_phone_standalone';SRC=OUT/'source-snapshot'
C='''#include <assert.h>
#include <stdio.h>
#include "imu_identity_policy.h"
int main(void){unsigned i,n=0;assert(IMU_AUTO_COMPAT_ID72==1);
for(i=0;i<256;i++){assert(imu_identity_allowed(i,IMU_AUTO_COMPAT_ID72)==(i==0x68||i==0x72));n++;
assert(imu_identity_allowed(i,0)==(i==0x68));n++;}
printf("{\\"result\\":\\"PASS\\",\\"identity_checks\\":%u,\\"physical_boot_tested\\":false}\\n",n);return 0;}'''
if __name__=='__main__':
 c=OUT/'imu-policy-check.c';exe=OUT/'imu-policy-check.exe';c.write_text(C,encoding='utf-8')
 subprocess.run([str(ROOT/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe'),'-I'+str(SRC),str(c),'-o',str(exe)],check=True)
 r=subprocess.run([str(exe)],capture_output=True,text=True,check=True);d=json.loads(r.stdout)
 (OUT/'boot-policy-checks.json').write_text(json.dumps(d,indent=2),encoding='utf-8');print(r.stdout.strip())
