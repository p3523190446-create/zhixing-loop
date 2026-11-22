/* Observer only. No motor, servo, GPIO, persistent storage or system calls. */
#include "imu_observer.h"
#include "imu_reference.h"
#include <math.h>
#include <string.h>
#define DEG 57.2957795131f
#define RAD 0.01745329252f
static float wrap(float x){while(x>180)x-=360;while(x<-180)x+=360;return x;}
static float magnitude(float x,float y,float z){return sqrtf(x*x+y*y+z*z);}
static void windows_clear(imu_observer_t *s)
{
 s->energy_at=s->energy_count=s->yaw_at=s->yaw_count=0;
 s->energy_sum=s->yaw_sum=s->rms=s->peak=s->yaw_window=0;s->window_ms=s->energy_time_total=0;
}
void imu_observer_init(imu_observer_t *s){memset(s,0,sizeof(*s));}
static void update_tilt(imu_observer_t *s,float tilt,uint32_t dt)
{
 if(!s->tilt_active){
  s->tilt_on_ms=tilt>=25?s->tilt_on_ms+dt:0;
  if(s->tilt_on_ms>=600){s->tilt_active=1;++s->tilt_count;s->tilt_on_ms=0;}
 }else{
  s->tilt_off_ms=tilt<=20?s->tilt_off_ms+dt:0;
  if(s->tilt_off_ms>=1000){s->tilt_active=0;s->tilt_off_ms=0;}
 }
 if(!s->extreme_active){
  s->extreme_on_ms=tilt>=60?s->extreme_on_ms+dt:0;
  if(s->extreme_on_ms>=600){s->extreme_active=1;s->extreme_on_ms=0;}
 }else{
  s->extreme_off_ms=tilt<=50?s->extreme_off_ms+dt:0;
  if(s->extreme_off_ms>=1000){s->extreme_active=0;s->extreme_off_ms=0;}
 }
}
void imu_observer_update(imu_observer_t *s,const int16_t raw[7],uint32_t now)
{
 float a[3],g[3],norm,ar,ap,dt,alpha,r,p,cp,sr,cr,yaw_rate=0,gravity[3],linear[3],dynamic,tilt;
 uint32_t elapsed=s->initialized?(uint32_t)(now-s->last_ms):0;unsigned i,saturated=0,same;
 if(s->initialized&&!elapsed)return; /* Never count the same MCU time twice. */
 s->now=now;s->flags=0;
 for(i=0;i<3;i++){a[i]=raw[i]/IMU_GRAVITY_RAW;g[i]=(raw[i+4]-IMU_GYRO_BIAS[i])/131.0f;}
 norm=magnitude(a[0],a[1],a[2]);
 for(i=0;i<6;i++){int n=raw[i<3?i:i+1];if(n>=32000||n<=-32000)saturated=1;}
 ar=atan2f(a[1],a[2])*DEG;ap=atan2f(-a[0],sqrtf(a[1]*a[1]+a[2]*a[2]))*DEG;
 if(!s->initialized||elapsed>250){
  s->roll=ar;s->pitch=ap;s->initialized=1;windows_clear(s);s->quiet_ms=0;
  s->tilt_on_ms=s->tilt_off_ms=s->extreme_on_ms=s->extreme_off_ms=s->lowg_ms=0;
  s->tilt_active=s->extreme_active=s->fall_active=0;
  s->identical_ms=0;s->last_rotation_ms=now;
  memcpy(s->previous_accel,a,sizeof(a));memcpy(s->previous_raw,raw,7*sizeof(*raw));
  s->last_ms=now;++s->count;return;
 }
 dt=elapsed*.001f;s->last_ms=now;++s->count;
 same=memcmp(s->previous_raw,raw,7*sizeof(*raw))==0;
 s->identical_ms=same?s->identical_ms+elapsed:0;memcpy(s->previous_raw,raw,7*sizeof(*raw));
 r=s->roll*RAD;p=s->pitch*RAD;sr=sinf(r);cr=cosf(r);cp=cosf(p);
 if(fabsf(cp)>.2f){
  float tangent=sinf(p)/cp;
  s->roll=wrap(s->roll+(g[0]+sr*tangent*g[1]+cr*tangent*g[2])*dt);
  s->pitch=wrap(s->pitch+(cr*g[1]-sr*g[2])*dt);
  yaw_rate=(sr*g[1]+cr*g[2])/cp;
 }else{s->roll=ar;s->pitch=ap;}
 alpha=.5f/(.5f+dt);
 if(fabsf(norm-1)<.15f){s->roll=wrap(s->roll+(1-alpha)*wrap(ar-s->roll));s->pitch=wrap(s->pitch+(1-alpha)*wrap(ap-s->pitch));}
 s->front_up=IMU_FRONT_SIGN*wrap(s->pitch-IMU_PITCH_REF);
 s->left_up=IMU_LEFT_SIGN*wrap(s->roll-IMU_ROLL_REF);
 s->gyro_z=yaw_rate;s->gyro_norm=magnitude(g[0],g[1],g[2]);
 r=s->roll*RAD;p=s->pitch*RAD;
 gravity[0]=-sinf(p);gravity[1]=sinf(r)*cosf(p);gravity[2]=cosf(r)*cosf(p);
 s->vertical=a[0]*gravity[0]+a[1]*gravity[1]+a[2]*gravity[2]-1;
 for(i=0;i<3;i++)linear[i]=a[i]-gravity[i];
 dynamic=magnitude(linear[0],linear[1],linear[2]);
 s->jerk=magnitude(a[0]-s->previous_accel[0],a[1]-s->previous_accel[1],a[2]-s->previous_accel[2])/dt;
 memcpy(s->previous_accel,a,sizeof(a));
 if(s->gyro_norm>8 || fabsf(cp)<.35f){s->flags|=IMU_ROTATING;s->last_rotation_ms=now;}
 /* Sideways force indicates acceleration/braking or turning: don't call it a road score. */
 if(magnitude(linear[0]-s->vertical*gravity[0],linear[1]-s->vertical*gravity[1],linear[2]-s->vertical*gravity[2])>.15f)s->flags|=IMU_ACCELERATING;
 if(saturated)s->flags|=IMU_SATURATED;
 if(s->identical_ms>=2000)s->flags|=IMU_FROZEN;
 if(norm>.5f&&dynamic>.35f&&s->jerk>2&&s->gyro_norm<30&&(!s->have_shock||(uint32_t)(now-s->last_shock_ms)>=500)){
  s->have_shock=1;s->last_shock_ms=now;++s->shock_count;
 }
 if(s->have_shock&&(uint32_t)(now-s->last_shock_ms)<2000)s->flags|=IMU_SHOCK_RECENT;
 s->lowg_ms=norm<.25f?s->lowg_ms+elapsed:0;
 if(s->lowg_ms>=150&&!s->fall_active){s->fall_active=1;++s->fall_count;}
 if(norm>.5f)s->fall_active=0;
 if(s->fall_active)s->flags|=IMU_FREEFALL;
 tilt=cosf((s->pitch-IMU_PITCH_REF)*RAD)*cosf((s->roll-IMU_ROLL_REF)*RAD);
 if(tilt>1.0f)tilt=1.0f;
 if(tilt< -1.0f)tilt= -1.0f;
 tilt=acosf(tilt)*DEG;
 if(norm>.5f)update_tilt(s,tilt,elapsed);
 if(s->tilt_active)s->flags|=IMU_TILT;
 if(s->extreme_active)s->flags|=IMU_EXTREME_TILT;
 if(dynamic<.025f&&s->gyro_norm<2&&s->jerk<.4f)s->quiet_ms+=elapsed;else s->quiet_ms=0;
 if(s->quiet_ms>=1000)s->flags|=IMU_LOW_DYNAMIC;
 /* Always bounded to approximately the latest 40 samples, never absolute heading. */
 if(fabsf(cp)>.35f){
  unsigned at=s->yaw_at;
  while(s->yaw_count){
   unsigned old=(at+IMU_WINDOW-s->yaw_count)%IMU_WINDOW;
   if((uint32_t)(now-s->yaw_times[old])<2000)break;
   s->yaw_sum-=s->yaw_steps[old];--s->yaw_count;
  }
  if(s->yaw_count==IMU_WINDOW)s->yaw_sum-=s->yaw_steps[at];else ++s->yaw_count;
  s->yaw_steps[at]=yaw_rate*dt;s->yaw_times[at]=now;s->yaw_sum+=s->yaw_steps[at];
  s->yaw_at=(at+1)%IMU_WINDOW;s->yaw_window=s->yaw_sum;
 }else{s->yaw_count=s->yaw_at=0;s->yaw_sum=s->yaw_window=0;}
 if(!(s->flags&(IMU_ROTATING|IMU_ACCELERATING|IMU_SATURATED|IMU_FROZEN|IMU_FREEFALL)) && (uint32_t)(now-s->last_rotation_ms)>=1000){
  unsigned at=s->energy_at;float value=s->vertical*s->vertical;
  while(s->energy_count){
   unsigned old=(at+IMU_WINDOW-s->energy_count)%IMU_WINDOW;
   if((uint32_t)(now-s->energy_times[old])<2000)break;
   s->energy_sum-=s->energy[old]*s->energy_dt[old];s->energy_time_total-=s->energy_dt[old];--s->energy_count;
  }
  if(s->energy_count==IMU_WINDOW){s->energy_sum-=s->energy[at]*s->energy_dt[at];s->energy_time_total-=s->energy_dt[at];}else ++s->energy_count;
  s->energy[at]=value;s->energy_dt[at]=elapsed;s->energy_times[at]=now;
  s->energy_sum+=value*elapsed;s->energy_time_total+=elapsed;s->energy_at=(at+1)%IMU_WINDOW;
  s->rms=sqrtf(s->energy_sum>0?s->energy_sum/s->energy_time_total:0);s->peak=0;
  for(i=0;i<s->energy_count;i++){
   unsigned slot=(s->energy_at+IMU_WINDOW-s->energy_count+i)%IMU_WINDOW;
   if(s->energy[slot]>s->peak)s->peak=s->energy[slot];
  }
  s->peak=sqrtf(s->peak);
  s->window_ms=s->energy_time_total;
  if(s->energy_count>=20&&s->window_ms>=1500)s->flags|=IMU_WINDOW_READY;
 }else{s->energy_at=s->energy_count=0;s->energy_sum=s->rms=s->peak=0;s->window_ms=s->energy_time_total=0;}
 if(!(s->flags&(IMU_SATURATED|IMU_FROZEN)))s->flags|=IMU_READY;
}
int imu_observer_valid(const imu_observer_t *s,uint32_t now)
{
 return s->initialized&&(s->flags&IMU_READY)&&(uint32_t)(now-s->now)<250;
}
