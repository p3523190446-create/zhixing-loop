#ifndef SERVO_PROBE_H
#define SERVO_PROBE_H
#include <stdint.h>
extern volatile uint32_t servo_probe_ready,servo_probe_active,servo_probe_pulse_us;
extern volatile uint32_t servo_probe_starts,servo_probe_stops,servo_probe_timer_hz;
void servo_probe_init(void);
void servo_probe_tick(uint32_t now);
int servo_probe_start(uint32_t now,unsigned wiggle);
void servo_probe_stop(void);
/* Fixed bounded patterns. Pulses are commands, not calibrated angles. */
static inline uint16_t servo_probe_pattern(uint32_t elapsed,unsigned wiggle)
{
    if(wiggle==2u){
        if(elapsed>=2500u)return 0;
        if(elapsed<500u)return 1500u;
        if(elapsed<1000u)return 1300u;
        if(elapsed<1500u)return 1500u;
        if(elapsed<2000u)return 1700u;
        return 1500u;
    }
    if(wiggle>2u || elapsed>=1000u)return 0;
    if(!wiggle)return 1500u;
    if(elapsed<200u)return 1500u;
    if(elapsed<400u)return 1400u;
    if(elapsed<600u)return 1500u;
    if(elapsed<800u)return 1600u;
    return 1500u;
}
#endif
