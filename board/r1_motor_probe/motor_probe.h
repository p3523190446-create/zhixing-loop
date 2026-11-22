#ifndef MOTOR_PROBE_H
#define MOTOR_PROBE_H
#include <stdint.h>
extern volatile uint32_t motor_rx_bytes,motor_rx_errors,motor_rx_drops;
extern volatile uint32_t motor_queries,motor_tx_bytes,motor_log_count,motor_last_rx_ms;
extern volatile uint8_t motor_log[128];
void motor_probe_init(void);
void motor_probe_poll(uint32_t now);
#endif
