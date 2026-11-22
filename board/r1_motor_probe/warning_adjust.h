#ifndef WARNING_ADJUST_H
#define WARNING_ADJUST_H
#include "guard.h"
/* This desk prototype uses 80/110 mm danger hysteresis. Keep caution above
 * that fixed boundary. Four Gray-code edges == one click was measured. */
static inline uint16_t warning_adjust(guard_t *guard, int64_t raw_cycles_delta)
{
    int64_t next=(int64_t)guard->config.caution_on_mm-raw_cycles_delta*10;
    if(next<120)next=120;
    if(next>500)next=500;
    if(next<=guard->config.danger_off_mm)return guard->config.caution_on_mm;
    guard->config.caution_on_mm=(uint16_t)next;
    guard->config.caution_off_mm=(uint16_t)(next+20);
    /* Do not reset last_good_ms, fault/recovery state or invent a sample.
     * The next real range result classifies with the new configuration. */
    return (uint16_t)next;
}
#endif
