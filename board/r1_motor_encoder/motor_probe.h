#ifndef MOTOR_PROBE_H
#define MOTOR_PROBE_H
#include <stdint.h>
extern volatile uint32_t motor_rx_bytes,motor_rx_errors,motor_rx_drops;
extern volatile uint32_t motor_queries,motor_tx_bytes,motor_log_count,motor_last_rx_ms;
extern volatile uint8_t motor_log[128];
extern volatile uint32_t motor_pulse_active,motor_pulse_count,motor_pulse_stops,motor_pulse_started_ms,motor_pulse_stopped_ms;
extern volatile uint32_t motor_pulse_channel;
extern volatile int32_t motor_encoder_counts[4];
extern volatile uint32_t motor_encoder_frames,motor_encoder_last_ms,motor_encoder_upload_enabled;
int motor_encoder_upload(uint32_t now,unsigned enable);
int motor_pulse_start(uint32_t now,unsigned channel);
void motor_probe_init(void);
void motor_probe_poll(uint32_t now);
#endif
