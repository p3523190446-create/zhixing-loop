#ifndef ZHIXING_WHEEL_CONTROL_H
#define ZHIXING_WHEEL_CONTROL_H
#include <stdint.h>
extern volatile int32_t wheel_outputs[4],wheel_targets[4];
extern volatile uint32_t wheel_fault;
void wheel_control_reset(void);
void wheel_control_stop(void);
uint32_t wheel_control_step(uint32_t now,int32_t left,int32_t right,const volatile int32_t speeds[4]);
#endif
