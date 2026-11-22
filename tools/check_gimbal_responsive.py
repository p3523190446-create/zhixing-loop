"""Execute the exact MCU manual_step; a position-perfect fake MCU cannot verify slew."""
from pathlib import Path
import json,subprocess
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'知行回路软件/build/r1_gimbal_responsive';SRC=OUT/'source-snapshot'
C=r'''
#include <assert.h>
#include <stdio.h>
#include "gimbal_random.h"
int main(void){
 gimbal_random_t r;uint32_t t;unsigned checks=0;uint16_t y,p;
 assert(manual_target_valid(500,2500)&&manual_target_valid(2500,500));checks++;
 assert(!manual_target_valid(499,1500)&&!manual_target_valid(1500,2501)&&!manual_target_valid(0xffffffffu,1500));checks++;
 random_init(&r,0);r.target_yaw=2500;r.target_pitch=500;
 for(t=1;t<=250;t++){y=r.yaw;p=r.pitch;manual_step(&r,t);assert(difference(y,r.yaw)<=40&&difference(p,r.pitch)<=40);assert(manual_target_valid(r.yaw,r.pitch));checks+=2;}
 assert(r.yaw==2500&&r.pitch==500);checks++;
 r.target_yaw=500;r.target_pitch=2500;
 for(t=260;t<=750;t+=10)manual_step(&r,t);
 assert(r.yaw==500&&r.pitch==2500);checks++;
 r.target_yaw=531;r.target_pitch=2497;manual_step(&r,760);
 assert(r.yaw==531&&r.pitch==2497);checks++;
 r.target_yaw=2500;r.target_pitch=500;y=r.yaw;p=r.pitch;manual_step(&r,1000000);
 assert(difference(y,r.yaw)==40&&difference(p,r.pitch)==40);checks++;
 random_init(&r,0);r.target_yaw=1700;r.target_pitch=1350;random_step(&r,10);
 assert(r.yaw==1501&&r.pitch==1499);checks++;
 assert(random_alive(&r,2999)&&!random_alive(&r,3000));checks++;
 printf("{\"result\":\"PASS\",\"checks\":%u,\"exact_mcu_header\":true,\"center_to_expanded_edge_ms\":250,\"physical_motion_tested\":false}\n",checks);
 return 0;
}'''
if __name__=='__main__':
 c=OUT/'responsive-check.c';exe=OUT/'responsive-check.exe';c.write_text(C,encoding='utf-8')
 subprocess.run([str(ROOT/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe'),'-I'+str(SRC),str(c),'-o',str(exe)],check=True)
 r=subprocess.run([str(exe)],check=True,capture_output=True,text=True);report=json.loads(r.stdout)
 (OUT/'responsive-checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(r.stdout.strip())
