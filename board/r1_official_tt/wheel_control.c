#include "wheel_control.h"
#include <string.h>
/* Command speed through Yahboom's encoder PID; CH32 owns permission and stop.
 * Outputs below are SPEED COMMANDS, never measured/applied PWM. */
typedef struct {int sign,phase;unsigned began,moved,brake;} wheel_t;
static wheel_t wheels[4];
volatile int32_t wheel_outputs[4],wheel_targets[4];
volatile uint32_t wheel_fault;
static int absolute(int x){return x<0?-x:x;}
void wheel_control_stop(void){unsigned i;memset(wheels,0,sizeof(wheels));for(i=0;i<4;i++)wheel_outputs[i]=wheel_targets[i]=0;}
void wheel_control_reset(void){wheel_control_stop();wheel_fault=0;}
static unsigned fault(unsigned code){wheel_control_stop();wheel_fault=code;return code;}
uint32_t wheel_control_step(uint32_t now,int32_t left,int32_t right,const volatile int32_t speeds[4])
{
    unsigned i;int peak=absolute(left)>absolute(right)?absolute(left):absolute(right);
    int outer=20+peak*100/250;if(wheel_fault)return wheel_fault;
    for(i=0;i<4;i++){
        wheel_t *w=&wheels[i];int input=i<2?left:right,speed=speeds[i];
        int sign=input>0?1:input<0?-1:0,wanted=peak?(outer*absolute(input)+peak/2)/peak:0;
        if(absolute(speed)>320)return fault(17+i);
        if(wanted<10)sign=0;
        if(!sign){memset(w,0,sizeof(*w));wheel_outputs[i]=wheel_targets[i]=0;continue;}
        wheel_targets[i]=sign*wanted;
        if(!w->phase||w->sign!=sign){
            if(w->phase!=3){w->brake=now;w->phase=3;}
            wheel_outputs[i]=0;
            if(w->sign||sign*speed < -8){
                if(absolute(speed)>8){if((unsigned)(now-w->brake)>800)return fault(49+i);continue;}
                if(w->sign&&(unsigned)(now-w->brake)<150)continue;
            }
            w->sign=sign;w->phase=1;w->began=w->moved=now;
        }
        if(sign*speed>8)w->moved=now;
        if((unsigned)(now-w->began)>=300&&sign*speed < -20)return fault(33+i);
        if((unsigned)(now-w->began)>=1000&&(unsigned)(now-w->moved)>=800)return fault(1+i);
        wheel_outputs[i]=sign*wanted;
    }
    return 0;
}
