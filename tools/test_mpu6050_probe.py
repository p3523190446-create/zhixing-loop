"""Run the actual C telemetry/failure paths with host GPIO stubs; no device access."""
from pathlib import Path
import json,subprocess
ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'知行回路软件/board/r1_mpu6050'
OUT=ROOT/'知行回路软件/build/r1_mpu6050/host-test';OUT.mkdir(parents=True,exist_ok=True)
(OUT/'debug.h').write_text('''#include <stdint.h>
typedef struct {unsigned GPIO_Pin,GPIO_Mode,GPIO_Speed;} GPIO_InitTypeDef;
#define GPIOD 0
#define GPIO_Pin_6 64
#define GPIO_Pin_7 128
#define RCC_APB2Periph_GPIOD 1
#define ENABLE 1
#define GPIO_Mode_Out_OD 1
#define GPIO_Speed_2MHz 2
void GPIO_SetBits(int,unsigned);void GPIO_ResetBits(int,unsigned);
unsigned GPIO_ReadInputDataBit(int,unsigned);
void Delay_Us(unsigned);void GPIO_Init(int,GPIO_InitTypeDef*);
void RCC_APB2PeriphClockCmd(int,int);
''',encoding='utf-8')
# The source's private state is visible in this TU so its output and fault
# transitions can be tested without implementing an unrelated I2C simulator.
source='''#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "debug.h"
static unsigned reads,mode,delays;
void GPIO_SetBits(int p,unsigned pins){assert(p==0 && !(pins&~192u));}
void GPIO_ResetBits(int p,unsigned pins){assert(p==0 && !(pins&~192u));}
unsigned GPIO_ReadInputDataBit(int p,unsigned pins){assert(p==0);reads++;return mode==1&&pins==64?0:1;}
void Delay_Us(unsigned us){delays+=us;assert(delays<100000);}
void GPIO_Init(int p,GPIO_InitTypeDef*g){assert(p==0&&g->GPIO_Pin==192&&g->GPIO_Mode==1);}
void RCC_APB2PeriphClockCmd(int p,int on){assert(p==1&&on==1);}
#include "mpu6050_probe.c"
static char answer[256];static void reply(const char*s){strcpy(answer,s);}
int main(void){
 mpu6050_probe_init(0);assert(!ready&&!samples);
 assert(mpu6050_probe_command("MPU_RAW",0,reply));assert(strstr(answer,"4294967295,0,")!=0);
 mpu6050_probe_poll(999);assert(!errors);
 mpu6050_probe_poll(1000);assert(errors==1&&last_error==3&&!ready&&!samples);
 mpu6050_probe_poll(1999);assert(errors==1);
 mode=1;reads=delays=0;mpu6050_probe_poll(2000);assert(errors==2&&last_error==1&&!ready&&reads<=60);
 mode=0;ready=1;samples=1;last_sample=0xfffffff0u;
 raw[0]=-32768;raw[1]=32767;raw[2]=16384;raw[3]=-340;raw[4]=-131;raw[5]=131;raw[6]=0;
 assert(mpu6050_probe_command("MPU_RAW",30,reply));
 assert(!strcmp(answer,"MPU_RAW,46,1,-32768,32767,16384,-340,-131,131,0\\n"));
 mpu6050_probe_command("MPU_RAW",234,reply);assert(strstr(answer,"250,0,")!=0);
 assert(!mpu6050_probe_command("DRIVE_ARM",30,reply));
 mpu6050_probe_command("MPU_ID",30,reply);assert(!strcmp(answer,"MPU_ID,MPU6050_PD6_PD7_ADDR69_V1\\n"));
 mpu6050_probe_command("MPU_COMPAT_ON",30,reply);assert(!strcmp(answer,"MPU_COMPAT_ON,REJECTED\\n"));
 identity=0x72;ready=0;mpu6050_probe_command("MPU_COMPAT_ON",30,reply);assert(compat_trial==1&&!strcmp(answer,"MPU_COMPAT_ON,TRIAL_ID72\\n"));
 ready=1;last_attempt=3000;delays=0;mpu6050_probe_poll(3050);assert(!ready&&errors==3);
 mpu6050_probe_command("MPU_RAW",3051,reply);assert(strstr(answer,",0,-32768,")!=0);
 puts("PASS: actual C NACK/clock-timeout/retry/freshness/wrap/signed output/no actuator handler");return 0;
}'''
# Include guard for the stub because the real source includes it too.
p=OUT/'debug.h';p.write_text('#ifndef TEST_DEBUG_H\n#define TEST_DEBUG_H\n'+p.read_text(encoding='utf-8')+'\n#endif\n',encoding='utf-8')
c=OUT/'test.c';c.write_text(source,encoding='utf-8');exe=OUT/'test.exe'
cc=ROOT/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe';steps=[]
for args in ([cc,'-Wall','-I'+str(OUT),'-I'+str(SRC),c,'-o',exe],[exe]):
    p=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=30)
    steps.append(dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));print(p.stdout+p.stderr,end='')
    if p.returncode:raise SystemExit(p.returncode)
(OUT/'verification.json').write_text(json.dumps(dict(result='PASS',scope='Actual C on host stubs, not hardware evidence',steps=steps),indent=2),encoding='utf-8')
