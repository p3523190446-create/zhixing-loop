#ifndef SERVO_PROBE_H
#define SERVO_PROBE_H
#include <stdint.h>
typedef struct {
    uint32_t ready,active,mode,yaw_us,pitch_us,starts,stops,yaw_hz,pitch_hz;
} gimbal_snapshot_t;
typedef struct {uint16_t yaw,pitch;} gimbal_pulses_t;
void servo_probe_init(void);
void servo_probe_tick(uint32_t now);
int servo_probe_start(uint32_t now,unsigned mode);
void servo_probe_stop(void);
void servo_probe_snapshot(gimbal_snapshot_t *out);
/* Fixed sequences only. A pulse width is not a calibrated physical angle. */
static inline gimbal_pulses_t gimbal_pattern(uint32_t elapsed,unsigned mode)
{
    gimbal_pulses_t p={0,0};unsigned stage;uint16_t single;
    if(mode<1u || mode>3u || elapsed>=2500u)return p;
    stage=elapsed/500u;
    if(mode<3u){
        single=stage==1u?1400u:(stage==3u?1600u:1500u);
        if(mode==1u)p.yaw=single;else p.pitch=single;
    }else{
        p.yaw=stage==1u?1600u:(stage==3u?1400u:1500u);
        p.pitch=stage==1u?1400u:(stage==3u?1600u:1500u);
    }
    return p;
}
#endif
