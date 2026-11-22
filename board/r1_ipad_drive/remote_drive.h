#ifndef ZHIXING_REMOTE_DRIVE_H
#define ZHIXING_REMOTE_DRIVE_H
#include <stdint.h>
extern volatile uint32_t remote_drive_armed,remote_drive_moving;
void remote_drive_tick(uint32_t now);
void remote_drive_poll(uint32_t now);
void remote_drive_stop(uint32_t reason);
int remote_drive_command(const char *command,uint32_t now,void (*reply)(const char *));
/* Implemented in the overlay of the existing USART3 driver. */
int motor_remote_write(int32_t left,int32_t right);
void motor_remote_stop_now(void);
#endif
