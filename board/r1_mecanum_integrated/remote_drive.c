#include "remote_drive.h"
#include "line_task_runtime.h"
#include "wheel_control.h"
#include "mecanum_mix.h"
#include "motor_probe.h"
#include <stdint.h>
#include <string.h>
#include <stdio.h>

/* User-operated manual filming. These are command amplitudes, not measured mm/s.
 * M1/M2 left, M3/M4 right per existing driver wiring. Ground direction still
 * requires physical verification and independent loss-of-wire stop hardware. */
#define DRIVE_MAX_PWM 250
#define DRIVE_LEASE_MS 600u
extern volatile uint32_t led_last_good_ms,range_correction_valid,range_corrected_mm,warning_mm;
volatile uint32_t remote_drive_armed,remote_drive_moving;
static volatile uint32_t generation,sequence,last_set,reason,dirty;
static volatile int32_t desired_left,desired_right;
static int32_t desired_wheels[4],desired_forward,desired_strafe,desired_turn;
static uint32_t controller_last;
volatile uint32_t remote_drive_uart_owner;
static volatile uint32_t seen_errors,seen_drops,error_changed_ms;

/* Reasons: 1 command expiry,2 range/obstacle,3 USB reset/suspend,
 * 4 driver stale/error,5 explicit stop,6 competing legacy test. */
static uint32_t blocked(uint32_t now)
{
    /* Official TT profile must be read from the real driver each boot. */
    if(!motor_profile_ready)return 8u;
    /* Explicit manual filming mode: range is advisory, including stale/invalid readings. */
    if(motor_rx_errors!=seen_errors||motor_rx_drops!=seen_drops||
       (uint32_t)(now-error_changed_ms)<1500u)return 4u;
    if(motor_voltage_mv<6000u||motor_voltage_mv>8500u)return 4u;
    if(!motor_voltage_frames||(uint32_t)(now-motor_voltage_last_ms)>=2500u||
       !motor_speed_frames||(uint32_t)(now-motor_speed_last_ms)>=600u||
       motor_speed_fault)return 4u;
    if(motor_pulse_active)return 6u;
    return 0u;
}
void remote_drive_stop(uint32_t why)
{
    remote_drive_armed=remote_drive_moving=remote_drive_uart_owner=0u;
    desired_left=desired_right=desired_forward=desired_strafe=desired_turn=0;
    memset(desired_wheels,0,sizeof(desired_wheels));dirty=0u;reason=why;
    wheel_control_stop();motor_remote_stop_now();
}
void remote_drive_tick(uint32_t now)
{
    uint32_t why;
    if(motor_rx_errors!=seen_errors||motor_rx_drops!=seen_drops){
        seen_errors=motor_rx_errors;seen_drops=motor_rx_drops;error_changed_ms=now;
        if(remote_drive_armed){remote_drive_stop(4u);return;}
    }
    if(!remote_drive_armed)return;
    if((uint32_t)(now-last_set)>=DRIVE_LEASE_MS){remote_drive_stop(1u);return;}
    why=blocked(now);if(why)remote_drive_stop(why);
}
void remote_drive_poll(uint32_t now)
{
    remote_drive_tick(now);
    if(!remote_drive_armed)return;
    if((uint32_t)(now-controller_last)<20u)return;
    controller_last=now;
    if(wheel_control_step4(now,desired_wheels,motor_speed_values)){remote_drive_stop(7u);return;}
    if(!remote_drive_armed){wheel_control_stop();return;}
    /* Fresh accepted vectors still expire after600ms. Feedback never renews it. */
    if(motor_remote_write4(wheel_outputs[0],wheel_outputs[1],wheel_outputs[2],wheel_outputs[3]))dirty=0u;
}
static int unsigned_number(const char **cursor,uint32_t *value,char terminator)
{
    uint32_t n=0u;const char *p=*cursor;
    if(*p<'0'||*p>'9')return 0;
    while(*p>='0'&&*p<='9'){
        uint32_t digit=(uint32_t)(*p-'0');
        if(n>(2147483647u-digit)/10u)return 0;
        n=n*10u+digit;++p;
    }
    if(*p!=terminator)return 0;
    *cursor=p+(terminator?1:0);*value=n;return 1;
}
static int pwm_number(const char **cursor,int32_t *value,char terminator)
{
    uint32_t n;int negative=0;
    if(**cursor=='-'){negative=1;++*cursor;}
    if(!unsigned_number(cursor,&n,terminator)||n>DRIVE_MAX_PWM)return 0;
    *value=negative?-(int32_t)n:(int32_t)n;return 1;
}
static int remote_drive_common(const char *command,uint32_t now,void (*reply)(const char *))
{
    char output[180];uint32_t gen,seq,why;int32_t left=0,right=0;const char *cursor;
    if(strncmp(command,"DRIVE_",6))return 0;
    if(!strcmp(command,"DRIVE_DIAG")){
        snprintf(output,sizeof(output),"DRIVEDIAG,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu\n",
          (unsigned long)now,(unsigned long)blocked(now),(unsigned long)range_corrected_mm,
          (unsigned long)warning_mm,(unsigned long)(now-led_last_good_ms),
          (unsigned long)motor_voltage_mv,(unsigned long)(now-motor_voltage_last_ms),
          (unsigned long)motor_speed_frames,(unsigned long)(now-motor_speed_last_ms),
          (unsigned long)motor_rx_errors,(unsigned long)motor_rx_drops,
          (unsigned long)(now-error_changed_ms),(unsigned long)motor_speed_fault);reply(output);return 1;
    }
    if(!strcmp(command,"DRIVE_ACTUATORS")){
        snprintf(output,sizeof(output),"ACTUATORS,%lu,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%lu\n",
            (unsigned long)now,(long)wheel_outputs[0],(long)wheel_outputs[1],(long)wheel_outputs[2],(long)wheel_outputs[3],
            (long)wheel_targets[0],(long)wheel_targets[1],(long)wheel_targets[2],(long)wheel_targets[3],(unsigned long)wheel_fault);
        reply(output);return 1;
    }
    if(!strcmp(command,"DRIVE_ID")){reply("DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_MECANUM_V2_20261107,1\n");return 1;}
    if(!strcmp(command,"DRIVE_PROFILE")){
        snprintf(output,sizeof(output),"DRIVE_PROFILE,%lu,%d,%d,%d,%d,%d,%d,%d,%d\n",
          (unsigned long)motor_profile_ready,motor_profile.type,motor_profile.deadzone,motor_profile.lines,motor_profile.ratio,
          motor_profile.diameter_milli,motor_profile.p_milli,motor_profile.i_milli,motor_profile.d_milli);reply(output);return 1;
    }
    if(!strcmp(command,"DRIVE_LIMITS")){reply("DRIVE_LIMITS,3600,0,0,1000\n");return 1;}
    if(!strcmp(command,"DRIVE_MODE")){reply("DRIVE_MODE,MANUAL,1,0\n");return 1;}
    if(!strcmp(command,"DRIVE_CAPS")){reply("DRIVE_CAPS,5,250,600\n");return 1;}
    if(!strcmp(command,"DRIVE_CHASSIS")){reply("DRIVE_CHASSIS,MECANUM_X,FL_RL_FR_RR,250,600\n");return 1;}
    if(!strcmp(command,"DRIVE_VECTOR_STATUS")){
        snprintf(output,sizeof(output),"DRIVE_VECTOR,%ld,%ld,%ld,%ld,%ld,%ld,%ld\n",
          (long)desired_forward,(long)desired_strafe,(long)desired_turn,
          (long)desired_wheels[0],(long)desired_wheels[1],(long)desired_wheels[2],(long)desired_wheels[3]);reply(output);return 1;
    }
    if(!strcmp(command,"DRIVE_STATUS")){
        snprintf(output,sizeof(output),"DRIVE,%lu,%lu,%lu,%lu,%lu,%ld,%ld,%lu,%lu\n",
          (unsigned long)now,(unsigned long)remote_drive_armed,(unsigned long)remote_drive_moving,
          (unsigned long)generation,(unsigned long)sequence,(long)desired_left,(long)desired_right,
          (unsigned long)reason,(unsigned long)(now-last_set));reply(output);return 1;
    }
    if(!strcmp(command,"DRIVE_STOP")){remote_drive_stop(5u);reply("DRIVE_STOPPED\n");return 1;}
    if(!strcmp(command,"DRIVE_ARM")){
        why=blocked(now);
        if(remote_drive_armed||why){reply("ERR,DRIVE_NOT_READY\n");return 1;}
        // Publish armed last, after an explicit zero target and a fresh generation.
        desired_left=desired_right=desired_forward=desired_strafe=desired_turn=0;memset(desired_wheels,0,sizeof(desired_wheels));
        dirty=0;reason=0;sequence=0;last_set=now;
        if(++generation>2147483647u)generation=1u;
        wheel_control_reset();controller_last=now-20u;motor_remote_stop_now();remote_drive_moving=0;remote_drive_armed=1;
        snprintf(output,sizeof(output),"DRIVE_ARMED,%lu\n",(unsigned long)generation);reply(output);return 1;
    }
    if(!strncmp(command,"DRIVE_VECTOR,",13)){
        int32_t f,x,r,targets[4];cursor=command+13;
        if(!unsigned_number(&cursor,&gen,',')||!unsigned_number(&cursor,&seq,',')||
           !pwm_number(&cursor,&f,',')||!pwm_number(&cursor,&x,',')||!pwm_number(&cursor,&r,0))goto invalid;
        if(!remote_drive_armed||gen!=generation||seq<=sequence||!seq)goto invalid;
        why=blocked(now);if(why){remote_drive_stop(why);goto invalid;}
        if(!mecanum_mix(f,x,r,targets))goto invalid;
        sequence=seq;desired_forward=f;desired_strafe=x;desired_turn=r;
        memcpy(desired_wheels,targets,sizeof(targets));desired_left=targets[0];desired_right=targets[2];
        last_set=now;reason=0;remote_drive_moving=f!=0||x!=0||r!=0;dirty=1;
        reply("DRIVE_VECTOR_ACCEPTED\n");return 1;
    }
    /* Preserve the deployed line task's two-side interface: strafe is zero. */
    if(!strncmp(command,"DRIVE_SET,",10)||!strncmp(command,"DRIVE_BRAKE,",12)){
        int brake=command[6]=='B';cursor=command+(brake?12:10);
        if(!unsigned_number(&cursor,&gen,',')||!unsigned_number(&cursor,&seq,brake?0:','))goto invalid;
        if(!brake&&(!pwm_number(&cursor,&left,',')||!pwm_number(&cursor,&right,0)))goto invalid;
        if(!remote_drive_armed||gen!=generation||seq<=sequence||!seq)goto invalid;
        why=blocked(now);if(why){remote_drive_stop(why);goto invalid;}
        sequence=seq;desired_left=left;desired_right=right;
        desired_wheels[0]=desired_wheels[1]=left;desired_wheels[2]=desired_wheels[3]=right;
        desired_forward=(left+right)/2;desired_strafe=0;desired_turn=(left-right)/2;
        last_set=now;reason=0;
        remote_drive_moving=left!=0||right!=0;
        if(brake){dirty=0;wheel_control_stop();motor_remote_stop_now();reply("DRIVE_BRAKED\n");}
        else{dirty=1;reply("DRIVE_SET_ACCEPTED\n");}
        return 1;
    }
invalid:
    reply("ERR,DRIVE_REJECTED\n");return 1;
}


static int task_accepted;
static void task_reply(const char *r){task_accepted=!strncmp(r,"DRIVE_ARMED,",12)||!strcmp(r,"DRIVE_SET_ACCEPTED\n");}
int remote_drive_task_begin(uint32_t now,int uart_owner){
 task_accepted=0;remote_drive_uart_owner=(uint32_t)uart_owner;remote_drive_common("DRIVE_ARM",now,task_reply);return task_accepted;
}
int remote_drive_task_set(uint32_t now,int left,int right){
 char c[96];task_accepted=0;
 if(left < -100||left > 100||right < -100||right > 100)return 0;
 snprintf(c,sizeof(c),"DRIVE_SET,%lu,%lu,%d,%d",(unsigned long)generation,(unsigned long)(sequence+1),left,right);
 remote_drive_common(c,now,task_reply);return task_accepted;
}

int remote_drive_command(const char *c,uint32_t n,void (*r)(const char *))
{if(line_task_running()&&(!strcmp(c,"DRIVE_ARM")||!strncmp(c,"DRIVE_SET,",10)||!strncmp(c,"DRIVE_VECTOR,",13)||!strncmp(c,"DRIVE_BRAKE,",12))){r("ERR,LINE_TASK_OWNS_DRIVE\n");return 1;}if(!strcmp(c,"DRIVE_ARM")&&!remote_drive_armed)remote_drive_uart_owner=0;return remote_drive_common(c,n,r);}
int remote_drive_uart_command(const char *c,uint32_t n,void (*r)(const char *))
{if(line_task_running()&&(!strcmp(c,"DRIVE_ARM")||!strncmp(c,"DRIVE_SET,",10)||!strncmp(c,"DRIVE_VECTOR,",13)||!strncmp(c,"DRIVE_BRAKE,",12))){r("ERR,LINE_TASK_OWNS_DRIVE\n");return 1;}if(!strcmp(c,"DRIVE_ARM")&&!remote_drive_armed)remote_drive_uart_owner=1;return remote_drive_common(c,n,r);}
