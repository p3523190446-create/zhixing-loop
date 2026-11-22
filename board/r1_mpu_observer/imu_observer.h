#ifndef IMU_OBSERVER_H
#define IMU_OBSERVER_H
#include <stdint.h>
#define IMU_WINDOW 40
enum {
 IMU_READY=1,IMU_LOW_DYNAMIC=2,IMU_TILT=4,IMU_EXTREME_TILT=8,
 IMU_SHOCK_RECENT=16,IMU_ROTATING=32,IMU_WINDOW_READY=64,
 IMU_SATURATED=128,IMU_FROZEN=256,IMU_FREEFALL=512,IMU_ACCELERATING=1024
};
typedef struct {
 uint32_t now,last_ms,count,flags,shock_count,tilt_count,fall_count;
 uint32_t last_shock_ms,last_rotation_ms,quiet_ms,tilt_on_ms,tilt_off_ms,extreme_on_ms,extreme_off_ms,lowg_ms;
 uint32_t identical_ms,energy_times[IMU_WINDOW],energy_dt[IMU_WINDOW],energy_time_total,yaw_times[IMU_WINDOW];
 unsigned initialized,tilt_active,extreme_active,fall_active,have_shock;
 unsigned energy_at,energy_count,yaw_at,yaw_count;
 int16_t previous_raw[7];
 float roll,pitch,front_up,left_up,gyro_z,gyro_norm,vertical,jerk,rms,peak,yaw_window;
 float previous_accel[3],energy[IMU_WINDOW],yaw_steps[IMU_WINDOW],energy_sum,yaw_sum;
 uint32_t window_ms;
} imu_observer_t;
void imu_observer_init(imu_observer_t *s);
void imu_observer_update(imu_observer_t *s,const int16_t raw[7],uint32_t now);
int imu_observer_valid(const imu_observer_t *s,uint32_t now);
#endif
