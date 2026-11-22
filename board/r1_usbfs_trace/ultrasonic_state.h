#ifndef ULTRASONIC_STATE_H
#define ULTRASONIC_STATE_H
#include <stdint.h>
/* status: 0 no sample, 1 valid, 2 timeout, 3 stuck high, 4 pulse range, 5 stale. */
typedef struct {
    uint32_t start_ms,last_good_ms,last_trigger_ms,trigger_count,good_count;
    uint32_t timeout_count,edge_count,reject_count,pulse_us,distance_mm;
    uint16_t rise_counter;
    uint8_t phase,status,valid;
} ultra_state_t;

static inline void ultra_expire(volatile ultra_state_t *u,uint32_t now)
{
    if(u->phase && (uint32_t)(now-u->start_ms)>=35u){
        u->phase=0;u->valid=0;u->status=2;u->pulse_us=0;
        u->distance_mm=0xffffffffu;++u->timeout_count;
    }
    if(u->valid && (uint32_t)(now-u->last_good_ms)>=300u){
        u->valid=0;u->status=5;u->distance_mm=0xffffffffu;
    }
}
static inline int ultra_begin(volatile ultra_state_t *u,uint32_t now,unsigned echo_high)
{
    if(u->phase || (uint32_t)(now-u->last_trigger_ms)<100u)return 0;
    u->last_trigger_ms=now;++u->trigger_count;
    if(echo_high){u->valid=0;u->status=3;u->distance_mm=0xffffffffu;++u->reject_count;return 0;}
    u->start_ms=now;u->phase=1;return 1;
}
static inline void ultra_edge(volatile ultra_state_t *u,uint32_t now,uint16_t counter,unsigned high)
{
    ++u->edge_count;
    ultra_expire(u,now);
    if(!u->phase){++u->reject_count;return;}
    if(high && u->phase==1){u->rise_counter=counter;u->phase=2;return;}
    if(!high && u->phase==2){
        uint32_t width=(uint16_t)(counter-u->rise_counter);
        u->phase=0;u->pulse_us=width;
        if(width<100u || width>18000u){u->valid=0;u->status=4;u->distance_mm=0xffffffffu;++u->reject_count;return;}
        /* 343m/s room-temperature approximation, not calibrated accuracy. */
        u->distance_mm=(width*343u+1000u)/2000u;
        u->last_good_ms=now;u->valid=1;u->status=1;++u->good_count;return;
    }
    ++u->reject_count;
}
#endif
