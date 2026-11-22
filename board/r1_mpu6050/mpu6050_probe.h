#ifndef MPU6050_PROBE_H
#define MPU6050_PROBE_H
#include <stdint.h>
void mpu6050_probe_init(uint32_t now);
void mpu6050_probe_poll(uint32_t now);
int mpu6050_probe_command(const char *command,uint32_t now,void (*reply)(const char *));
#endif
