#ifndef GIMBAL_RANDOM_H
#define GIMBAL_RANDOM_H
#include <stdint.h>
typedef struct {
    uint32_t random,last_step_ms,last_keepalive_ms,targets;
    uint16_t yaw,pitch,target_yaw,target_pitch;
} gimbal_random_t;
static inline uint32_t random_next(gimbal_random_t *r)
{
    r->random=r->random*1664525u+1013904223u;return r->random;
}
static inline unsigned difference(uint16_t a,uint16_t b){return a>b?a-b:b-a;}
static inline void random_target(gimbal_random_t *r)
{
    unsigned i;uint16_t y=1500,p=1500;
    for(i=0;i<12;i++){
        y=(uint16_t)(1300u+random_next(r)%401u);
        p=(uint16_t)(1350u+random_next(r)%301u);
        if(difference(y,r->yaw)>=80u && difference(p,r->pitch)>=60u)break;
    }
    if(difference(y,r->yaw)<80u)y=r->yaw<=1500u?1700u:1300u;
    if(difference(p,r->pitch)<60u)p=r->pitch<=1500u?1650u:1350u;
    r->target_yaw=y;r->target_pitch=p;++r->targets;
}
static inline void random_init(gimbal_random_t *r,uint32_t now)
{
    r->random=now^0x35b49f01u;r->yaw=1500u;r->pitch=1500u;
    r->last_keepalive_ms=now;r->last_step_ms=now;r->targets=0;random_target(r);
}
static inline int random_alive(const gimbal_random_t *r,uint32_t now)
{
    return (uint32_t)(now-r->last_keepalive_ms)<3000u;
}
static inline void random_step(gimbal_random_t *r,uint32_t now)
{
    if((uint32_t)(now-r->last_step_ms)<10u)return;
    r->last_step_ms=now;
    /* One microsecond per 10ms, never catch up with a large jump after a delay. */
    if(r->yaw<r->target_yaw)++r->yaw;else if(r->yaw>r->target_yaw)--r->yaw;
    if(r->pitch<r->target_pitch)++r->pitch;else if(r->pitch>r->target_pitch)--r->pitch;
    if(r->yaw==r->target_yaw && r->pitch==r->target_pitch)random_target(r);
}
static inline int manual_target_valid(uint32_t yaw,uint32_t pitch)
{
    return yaw>=500u && yaw<=2500u && pitch>=500u && pitch<=2500u;
}
/* Manual mode: up to40us each10ms (4000us/s), no delayed catch-up.
 * Random mode and the independent3000ms watchdog remain unchanged. */
static inline uint16_t manual_toward(uint16_t value,uint16_t target)
{
    if(value<target)return target-value>40?(uint16_t)(value+40u):target;
    if(value>target)return value-target>40?(uint16_t)(value-40u):target;
    return value;
}
static inline void manual_step(gimbal_random_t *r,uint32_t now)
{
    if((uint32_t)(now-r->last_step_ms)<10u)return;
    r->last_step_ms=now;
    r->yaw=manual_toward(r->yaw,r->target_yaw);
    r->pitch=manual_toward(r->pitch,r->target_pitch);
}
#endif
