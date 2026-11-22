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
extern volatile uint8_t motor_parameter_raw[384];
extern volatile uint32_t motor_parameter_bytes,motor_parameter_capture;
extern volatile int32_t motor_speed_values[4],motor_speed_min,motor_speed_max,motor_speed_sum;
extern volatile uint32_t motor_speed_frames,motor_speed_last_ms,motor_speed_mode,motor_speed_fault,motor_speed_samples;
extern volatile int32_t motor_speed_count_first,motor_speed_count_last;
extern volatile uint32_t motor_speed_time_first,motor_speed_time_last;
extern volatile int32_t motor_control_speed,motor_control_pwm;
extern volatile uint32_t motor_control_updates;
extern volatile uint32_t motor_fault_cause,motor_fault_ms,motor_fault_elapsed,motor_fault_channel,motor_fault_mode;
extern volatile int32_t motor_fault_driver_speed,motor_fault_filtered_speed,motor_fault_pwm;
extern volatile uint32_t motor_fault_streak;
int motor_closed_start(uint32_t now,unsigned channel);
int motor_calibration_start(uint32_t now,unsigned channel,unsigned level);
int motor_speed_start(uint32_t now,unsigned channel);
void motor_stop(void);
int motor_parameter_write(uint32_t now,unsigned parameter);
int motor_parameter_read(uint32_t now);
int motor_encoder_upload(uint32_t now,unsigned enable);
int motor_pulse_start(uint32_t now,unsigned channel);
void motor_probe_init(void);
void motor_probe_poll(uint32_t now);
#endif
