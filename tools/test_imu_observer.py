"""Exercise the actual portable MCU observer with controlled signals, not real-road evidence."""
from pathlib import Path
import json,subprocess,sys
ROOT=Path(__file__).resolve().parents[2];SRC=ROOT/'知行回路软件/board/r1_mpu_observer'
OUT=ROOT/'知行回路软件/build/r1_imu_observer/host-test';OUT.mkdir(parents=True,exist_ok=True)
test=r'''
#include "imu_observer.h"
#include "imu_reference.h"
#include <math.h>
#include <assert.h>
#include <stdio.h>
#define RAD 0.01745329252f
static unsigned tick;
static int16_t integer(float x){return (int16_t)(x+(x>=0?.5f:-.5f));}
static void sample(imu_observer_t*s,uint32_t now,float roll,float pitch,float norm,float gz,int jitter){
 int16_t raw[7];float r=roll*RAD,p=pitch*RAD;
 raw[0]=integer(-sinf(p)*IMU_GRAVITY_RAW*norm);raw[1]=integer(sinf(r)*cosf(p)*IMU_GRAVITY_RAW*norm);
 raw[2]=integer(cosf(r)*cosf(p)*IMU_GRAVITY_RAW*norm);raw[3]=3504;
 raw[4]=integer(IMU_GYRO_BIAS[0]);raw[5]=integer(IMU_GYRO_BIAS[1]);raw[6]=integer(IMU_GYRO_BIAS[2]+gz*131);
 if(jitter){raw[3]+=(++tick)%5;raw[0]+=(int)(tick%3)-1;}
 imu_observer_update(s,raw,now);
}
static void steady(imu_observer_t*s,uint32_t*now,unsigned n,float roll,float pitch,float norm,float gz){
 while(n--){*now+=50;sample(s,*now,roll,pitch,norm,gz,1);}
}
int main(void){
 imu_observer_t s;uint32_t t=0;unsigned i,n;imu_observer_init(&s);
 steady(&s,&t,120,IMU_ROLL_REF,IMU_PITCH_REF,1,0);
 assert(imu_observer_valid(&s,t)&&(s.flags&IMU_LOW_DYNAMIC)&&(s.flags&IMU_WINDOW_READY));
 assert(fabsf(s.front_up)<.1f&&fabsf(s.left_up)<.1f&&s.rms<.003f&&fabsf(s.yaw_window)<.1f);
 steady(&s,&t,160,IMU_ROLL_REF,IMU_PITCH_REF-15,1,0);
 assert(s.front_up>14.8f&&s.front_up<15.2f&&fabsf(s.left_up)<.2f&&s.rms<.01f);
 imu_observer_init(&s);t=0;steady(&s,&t,80,IMU_ROLL_REF,IMU_PITCH_REF,1,0);
 for(i=0;i<120;i++){t+=50;sample(&s,t,IMU_ROLL_REF,IMU_PITCH_REF,1+.12f*sinf(i*.314159265f),0,1);}
 assert((s.flags&IMU_WINDOW_READY)&&s.rms>.06f&&s.rms<.10f&&s.peak>.10f&&s.shock_count==0);
 t+=50;sample(&s,t,IMU_ROLL_REF,IMU_PITCH_REF,1.6f,0,1);assert(s.shock_count==1&&(s.flags&IMU_SHOCK_RECENT));
 steady(&s,&t,2,IMU_ROLL_REF,IMU_PITCH_REF,1.6f,0);assert(s.shock_count==1);
 steady(&s,&t,120,IMU_ROLL_REF+35,IMU_PITCH_REF,1,0);assert(s.flags&IMU_TILT);n=s.tilt_count;
 steady(&s,&t,80,IMU_ROLL_REF+23,IMU_PITCH_REF,1,0);assert(s.flags&IMU_TILT);assert(s.tilt_count==n);
 steady(&s,&t,120,IMU_ROLL_REF,IMU_PITCH_REF,1,0);assert(!(s.flags&IMU_TILT));
 steady(&s,&t,120,IMU_ROLL_REF+75,IMU_PITCH_REF,1,0);assert(s.flags&IMU_EXTREME_TILT);
 imu_observer_init(&s);t=0;steady(&s,&t,80,IMU_ROLL_REF,IMU_PITCH_REF,1,0);
 steady(&s,&t,4,IMU_ROLL_REF,IMU_PITCH_REF,0,0);assert(s.fall_count==1&&(s.flags&IMU_FREEFALL)&&s.shock_count==0&&imu_observer_valid(&s,t));
 steady(&s,&t,4,IMU_ROLL_REF,IMU_PITCH_REF,1,0);assert(!(s.flags&IMU_FREEFALL));
 imu_observer_init(&s);t=0;steady(&s,&t,100,IMU_ROLL_REF,IMU_PITCH_REF,1,30);
 assert((s.flags&IMU_ROTATING)&&!(s.flags&IMU_WINDOW_READY)&&s.yaw_window>55&&s.yaw_window<65);
 t+=1000;sample(&s,t,IMU_ROLL_REF,IMU_PITCH_REF,1,0,1);assert(!s.energy_count&&!s.yaw_count&&!imu_observer_valid(&s,t));
 imu_observer_init(&s);t=0xffffff00u;steady(&s,&t,100,IMU_ROLL_REF,IMU_PITCH_REF,1,0);
 assert(imu_observer_valid(&s,t)&&!imu_observer_valid(&s,t+250));n=s.count;sample(&s,t,IMU_ROLL_REF,IMU_PITCH_REF,1,0,1);assert(s.count==n);
 for(i=0;i<45;i++){t+=50;sample(&s,t,IMU_ROLL_REF,IMU_PITCH_REF,1,0,0);}
 assert((s.flags&IMU_FROZEN)&&!imu_observer_valid(&s,t));
 {int16_t raw[7]={0,0,32767,3504,-1968,12,-128};t+=50;imu_observer_update(&s,raw,t);assert((s.flags&IMU_SATURATED)&&!imu_observer_valid(&s,t));}
 imu_observer_init(&s);t=0;steady(&s,&t,80,IMU_ROLL_REF,IMU_PITCH_REF,1.1f,0);
 for(i=0;i<80;i++){t+=(i%2?80:20);sample(&s,t,IMU_ROLL_REF,IMU_PITCH_REF,1.1f,0,1);}
 assert((s.flags&IMU_WINDOW_READY)&&s.rms>.098f&&s.rms<.102f&&s.window_ms>=1900&&s.window_ms<=2080);
 puts("PASS: actual MCU core stationary/slope/vibration/shock/hysteresis/extreme/freefall/rotation/gap/wrap/duplicate/frozen/saturation/variable-cadence");
 return 0;
}
'''
(OUT/'math.h').write_text('''/* Host CRT adapters: TCC's bundled x87 inline fabs is unsupported on Win64. */
double sqrt(double);double sin(double);double cos(double);double atan2(double,double);double acos(double);
#define sqrtf(x) ((float)sqrt((double)(x)))
#define sinf(x) ((float)sin((double)(x)))
#define cosf(x) ((float)cos((double)(x)))
#define atan2f(y,x) ((float)atan2((double)(y),(double)(x)))
#define acosf(x) ((float)acos((double)(x)))
#define fabsf(x) ((x)<0?-(x):(x))
''',encoding='utf-8')
c=OUT/'test.c';c.write_text(test,encoding='utf-8');exe=OUT/'test.exe';cc=ROOT/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe'
steps=[]
for args in ([cc,'-Wall','-I'+str(OUT),'-I'+str(SRC),c,SRC/'imu_observer.c','-o',exe],[exe]):
    p=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=30)
    steps.append(dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));print(p.stdout+p.stderr,end='')
    if p.returncode:raise SystemExit(p.returncode)
(OUT/'verification.json').write_text(json.dumps(dict(result='PASS',scope='Controlled synthetic signals applied to actual MCU C core; not physical road/collision/fall proof',steps=steps),indent=2)+'\n',encoding='utf-8')
