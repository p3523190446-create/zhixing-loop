#ifndef MOTOR_TELEMETRY_H
#define MOTOR_TELEMETRY_H
#include <stdint.h>
#include <string.h>
/* Exact fixed-point voltage parsing; no float rounding or fractional-scale guess. */
static inline int motor_parse_voltage(const char *p,uint32_t *mv)
{
    uint32_t whole=0,frac=0,scale=100;unsigned n=0,d=0;
    if(strncmp(p,"$Battery:",9))return 0;
    p+=9;
    while(*p>='0' && *p<='9'){
        if(++n>2)return 0;
        whole=whole*10u+(unsigned)(*p++-'0');
    }
    if(!n || *p++!='.')return 0;
    while(*p>='0' && *p<='9'){
        if(++d>3)return 0;
        frac+=(unsigned)(*p++-'0')*scale;scale/=10u;
    }
    if(!d || strcmp(p,"V#") || whole>20u || (whole==20u && frac))return 0;
    *mv=whole*1000u+frac;return 1;
}
static inline int motor_value_fresh(uint32_t now,uint32_t last,uint32_t seen,uint32_t limit)
{return seen && (uint32_t)(now-last)<=limit;}
/* 0 no fresh wheel data; 1 stationary feedback; 2 moving; 3 latched/serial/voltage fault. */
static inline unsigned motor_dashboard_state(int speed_fresh,const int32_t *speeds,
    unsigned active,unsigned fault,unsigned errors,unsigned drops,int voltage_fresh,uint32_t mv)
{
    unsigned i;
    if(!speed_fresh)return 0;
    if(fault || errors || drops || (voltage_fresh && (mv<6000u || mv>8500u)))return 3;
    if(active)return 2;
    for(i=0;i<4;i++)if(speeds[i]>5 || speeds[i]<-5)return 2;
    return 1;
}
#endif
