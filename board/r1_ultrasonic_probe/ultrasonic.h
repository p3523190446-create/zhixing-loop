#ifndef ULTRASONIC_H
#define ULTRASONIC_H
#include "ultrasonic_state.h"
extern volatile ultra_state_t ultrasonic_state;
extern volatile uint32_t ultrasonic_timer_hz;
void ultrasonic_init(void);
void ultrasonic_tick(uint32_t now);
void ultrasonic_poll(uint32_t now);
void ultrasonic_snapshot(ultra_state_t *out);
#endif
