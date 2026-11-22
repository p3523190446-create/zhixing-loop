#ifndef IMU_IDENTITY_POLICY_H
#define IMU_IDENTITY_POLICY_H
#include <stdint.h>
/* The installed0x69 device reports0x72 and uses the saved ID72 reference.
 * Accepted by this car's integration; this does not identify it as genuine MPU6050. */
#define IMU_AUTO_COMPAT_ID72 1u
static inline int imu_identity_allowed(uint8_t id,uint8_t allow72)
{return id==0x68u||(id==0x72u&&allow72);}
#endif
