#ifndef ZHIXING_VL53L0X_PLATFORM_H
#define ZHIXING_VL53L0X_PLATFORM_H
#include "vl53l0x_def.h"
#include "vl53l0x_platform_log.h"
#define VL53L0X_COPYSTRING(destination, source) strcpy((destination), (source))
typedef struct {
    VL53L0X_DevData_t Data;
    uint8_t I2cDevAddr; /* ST API convention: 8-bit write address, 0x52. */
} VL53L0X_Dev_t;
typedef VL53L0X_Dev_t *VL53L0X_DEV;
#define PALDevDataGet(Dev, field) ((Dev)->Data.field)
#define PALDevDataSet(Dev, field, value) ((Dev)->Data.field = (value))
void range_bus_init(void);
VL53L0X_Error VL53L0X_LockSequenceAccess(VL53L0X_DEV);
VL53L0X_Error VL53L0X_UnlockSequenceAccess(VL53L0X_DEV);
VL53L0X_Error VL53L0X_WriteMulti(VL53L0X_DEV,uint8_t,uint8_t *,uint32_t);
VL53L0X_Error VL53L0X_ReadMulti(VL53L0X_DEV,uint8_t,uint8_t *,uint32_t);
VL53L0X_Error VL53L0X_WrByte(VL53L0X_DEV,uint8_t,uint8_t);
VL53L0X_Error VL53L0X_WrWord(VL53L0X_DEV,uint8_t,uint16_t);
VL53L0X_Error VL53L0X_WrDWord(VL53L0X_DEV,uint8_t,uint32_t);
VL53L0X_Error VL53L0X_RdByte(VL53L0X_DEV,uint8_t,uint8_t *);
VL53L0X_Error VL53L0X_RdWord(VL53L0X_DEV,uint8_t,uint16_t *);
VL53L0X_Error VL53L0X_RdDWord(VL53L0X_DEV,uint8_t,uint32_t *);
VL53L0X_Error VL53L0X_UpdateByte(VL53L0X_DEV,uint8_t,uint8_t,uint8_t);
VL53L0X_Error VL53L0X_PollingDelay(VL53L0X_DEV);
#endif
