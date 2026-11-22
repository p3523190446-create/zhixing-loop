#ifndef DISTANCE_TREND_H
#define DISTANCE_TREND_H
#include <stdint.h>
#include <string.h>
enum { TREND_UNKNOWN, TREND_STILL, TREND_CLOSING, TREND_AWAY };
typedef struct {
    uint32_t times[7],last_ms;
    uint16_t ranges[7];
    uint8_t count,valid,kind;
    int32_t closing_mm_s;
} distance_trend_t;
static inline void distance_trend_reset(distance_trend_t *s)
{memset(s,0,sizeof(*s));}
static inline void distance_trend_expire(distance_trend_t *s,uint32_t now)
{if(s->count && (uint32_t)(now-s->last_ms)>=300u)distance_trend_reset(s);}
static inline void distance_trend_sample(distance_trend_t *s,uint32_t now,int valid,uint16_t mm)
{
    unsigned i;uint32_t dt;
    int32_t delta,v;
    if(!valid){distance_trend_reset(s);return;}
    distance_trend_expire(s,now);
    if(s->count && now==s->last_ms)return;
    if(s->count==7){
        for(i=0;i<6;i++){s->times[i]=s->times[i+1];s->ranges[i]=s->ranges[i+1];}
        s->count=6;
    }
    s->times[s->count]=now;s->ranges[s->count]=mm;++s->count;s->last_ms=now;
    if(s->count<7)return;
    /* Difference of two-point means at the ends of the window. Relative
     * timestamps handle the 32-bit clock wrap; no assumed sample period. */
    dt=(uint32_t)(s->times[5]-s->times[0])+(uint32_t)(s->times[6]-s->times[0])-(uint32_t)(s->times[1]-s->times[0]);
    if(dt<600u){s->valid=0;s->kind=TREND_UNKNOWN;return;}
    delta=(int32_t)s->ranges[0]+s->ranges[1]-s->ranges[5]-s->ranges[6];
    v=delta*1000/(int32_t)dt;s->closing_mm_s=v;s->valid=1;
    if(v>=40)s->kind=TREND_CLOSING;
    else if(v<=-40)s->kind=TREND_AWAY;
    else if(v>=-25 && v<=25)s->kind=TREND_STILL;
    else if(s->kind==TREND_UNKNOWN)s->kind=TREND_STILL;
    /* Indication only: no warning permission or motor control here. */
}
#endif
