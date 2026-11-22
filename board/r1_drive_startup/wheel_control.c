#include "wheel_control.h"
#include <string.h>

/* Suspended bench only. Raw driver speed units, not calibrated vehicle cm/s.
 * One bounded breakaway per zero->motion transition. No repeated auto kicks.
 * A stalled/overspeed/reversed-feedback wheel stops the whole drive session. */
#define KICK_PWM 375
#define KICK_MS 300u
#define CONTROL_MS 100u
#define STALL_MS 1000u
typedef struct {int sign,phase;int32_t integral;uint32_t began,last,moved,brake;} wheel_t;
static wheel_t wheels[4];
/* Initial feedforward from prior per-wheel120-speed bench; PI corrects it.
 * These constants are starting estimates, not fresh loaded calibration. */
static const int32_t feed120[4]={232,163,224,173};
static const int32_t friction[4]={150,100,150,100};
volatile int32_t wheel_outputs[4],wheel_targets[4];
volatile uint32_t wheel_fault;
static int32_t absolute(int32_t x){return x<0?-x:x;}
static int32_t bound(int32_t x,int32_t lo,int32_t hi){return x<lo?lo:x>hi?hi:x;}
void wheel_control_stop(void)
{
    unsigned i;memset(wheels,0,sizeof(wheels));
    for(i=0;i<4u;i++)wheel_outputs[i]=wheel_targets[i]=0;
}
void wheel_control_reset(void){wheel_control_stop();wheel_fault=0;}
static uint32_t fault(uint32_t code)
{wheel_control_stop();wheel_fault=code;return code;}
uint32_t wheel_control_step(uint32_t now,int32_t left,int32_t right,const volatile int32_t speeds[4])
{
    unsigned i;
    if(wheel_fault)return wheel_fault;
    for(i=0;i<4u;i++){
        wheel_t *w=&wheels[i];int32_t input=i<2u?left:right;
        int32_t speed=speeds[i],sign=input>0?1:input<0?-1:0;
        int32_t wanted=80+absolute(input)*40/250,aligned,error,ff,pwm;
        if(absolute(speed)>320)return fault(16u+i+1u);
        if(!sign){memset(w,0,sizeof(*w));wheel_outputs[i]=wheel_targets[i]=0;continue;}
        wanted=bound(wanted,80,120);wheel_targets[i]=sign*wanted;
        if(!w->phase || w->sign!=sign){
            if(w->phase!=3){w->brake=now;w->phase=3;}
            wheel_outputs[i]=0;
            /* Always brake before reversing; coast feedback must actually settle. */
            if(absolute(speed)>8){if((uint32_t)(now-w->brake)>800u)return fault(48u+i+1u);continue;}
            if(w->sign && (uint32_t)(now-w->brake)<150u)continue;
            w->sign=sign;w->phase=1;w->began=w->last=w->moved=now;w->integral=0;
        }
        aligned=sign*speed;
        if(aligned>8)w->moved=now;
        if((uint32_t)(now-w->began)>=300u && aligned < -20)return fault(32u+i+1u);
        if((uint32_t)(now-w->began)>=STALL_MS && (uint32_t)(now-w->moved)>=800u)return fault(i+1u);
        if((uint32_t)(now-w->began)<KICK_MS){wheel_outputs[i]=sign*KICK_PWM;continue;}
        if(w->phase==2 && (uint32_t)(now-w->last)<CONTROL_MS)continue;
        w->phase=2;w->last=now;error=wanted-aligned;
        w->integral=bound(w->integral+error*20,-160*256,160*256);
        ff=friction[i]+(feed120[i]-friction[i])*wanted/120;
        pwm=bound(ff+error/3+w->integral/256,0,KICK_PWM);
        wheel_outputs[i]=sign*pwm;
    }
    return 0;
}
