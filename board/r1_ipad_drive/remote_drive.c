#include "remote_drive.h"
#include "motor_probe.h"
#include <stdint.h>
#include <string.h>
#include <stdio.h>

/* Suspension/bench only. These are command amplitudes, not measured mm/s.
 * M1/M2 left, M3/M4 right per existing driver wiring. Ground direction still
 * requires physical verification and independent loss-of-wire stop hardware. */
#define DRIVE_MAX_PWM 250
#define DRIVE_LEASE_MS 600u
extern volatile uint32_t led_last_good_ms,range_correction_valid,range_corrected_mm,warning_mm;
volatile uint32_t remote_drive_armed,remote_drive_moving;
static volatile uint32_t generation,sequence,last_set,reason,dirty;
static volatile int32_t desired_left,desired_right;

/* Reasons: 1 command expiry,2 range/obstacle,3 USB reset/suspend,
 * 4 driver stale/error,5 explicit stop,6 competing legacy test. */
static uint32_t blocked(uint32_t now)
{
    if(!range_correction_valid||(uint32_t)(now-led_last_good_ms)>=300u||range_corrected_mm<=warning_mm)return 2u;
    if(!motor_voltage_frames||(uint32_t)(now-motor_voltage_last_ms)>=2500u||
       !motor_speed_frames||(uint32_t)(now-motor_speed_last_ms)>=600u||
       motor_rx_errors||motor_rx_drops||motor_speed_fault)return 4u;
    if(motor_pulse_active)return 6u;
    return 0u;
}
void remote_drive_stop(uint32_t why)
{
    remote_drive_armed=remote_drive_moving=0u;
    desired_left=desired_right=0;dirty=0u;reason=why;
    motor_remote_stop_now();
}
void remote_drive_tick(uint32_t now)
{
    uint32_t why;
    if(!remote_drive_armed)return;
    if((uint32_t)(now-last_set)>=DRIVE_LEASE_MS){remote_drive_stop(1u);return;}
    why=blocked(now);if(why)remote_drive_stop(why);
}
void remote_drive_poll(uint32_t now)
{
    remote_drive_tick(now);
    if(remote_drive_armed&&dirty&&motor_remote_write(desired_left,desired_right))dirty=0u;
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
int remote_drive_command(const char *command,uint32_t now,void (*reply)(const char *))
{
    char output[180];uint32_t gen,seq,why;int32_t left=0,right=0;const char *cursor;
    if(strncmp(command,"DRIVE_",6))return 0;
    if(!strcmp(command,"DRIVE_CAPS")){reply("DRIVE_CAPS,1,250,600\n");return 1;}
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
        desired_left=desired_right=0;dirty=0;reason=0;sequence=0;last_set=now;
        if(++generation>2147483647u)generation=1u;
        motor_remote_stop_now();remote_drive_moving=0;remote_drive_armed=1;
        snprintf(output,sizeof(output),"DRIVE_ARMED,%lu\n",(unsigned long)generation);reply(output);return 1;
    }
    if(!strncmp(command,"DRIVE_SET,",10)||!strncmp(command,"DRIVE_BRAKE,",12)){
        int brake=command[6]=='B';cursor=command+(brake?12:10);
        if(!unsigned_number(&cursor,&gen,',')||!unsigned_number(&cursor,&seq,brake?0:','))goto invalid;
        if(!brake&&(!pwm_number(&cursor,&left,',')||!pwm_number(&cursor,&right,0)))goto invalid;
        if(!remote_drive_armed||gen!=generation||seq<=sequence||!seq)goto invalid;
        why=blocked(now);if(why){remote_drive_stop(why);goto invalid;}
        sequence=seq;desired_left=left;desired_right=right;last_set=now;reason=0;
        remote_drive_moving=left!=0||right!=0;
        if(brake){dirty=0;motor_remote_stop_now();reply("DRIVE_BRAKED\n");}
        else{dirty=1;reply("DRIVE_SET_ACCEPTED\n");}
        return 1;
    }
invalid:
    reply("ERR,DRIVE_REJECTED\n");return 1;
}
