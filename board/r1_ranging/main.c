#include "debug.h"
#include "vl53l0x_api.h"
#include <string.h>

/* Raw distance experiment, not yet the competition warning application. */
static VL53L0X_Dev_t device;
volatile uint32_t range_stage, range_rounds, range_valid_count;
volatile int32_t range_init_error, range_error;
volatile uint32_t range_status=255, range_mm=0xFFFFFFFFu, range_model_id;
typedef struct { uint32_t round, mm, status; int32_t error; } RangeRecord;
volatile RangeRecord range_history[32];
volatile uint32_t range_history_count;

/* MCU resets do not necessarily power-cycle the sensor. Follow ST's soft
 * reset sequence with bounded waits instead of its unbounded reference loops. */
static VL53L0X_Error reset_sensor(void)
{
    unsigned i;
    uint8_t id=0xFF;
    VL53L0X_Error e=VL53L0X_WrByte(&device,VL53L0X_REG_SOFT_RESET_GO2_SOFT_RESET_N,0);
    if(e)return e;
    for(i=0;i<100;i++){
        e=VL53L0X_RdByte(&device,VL53L0X_REG_IDENTIFICATION_MODEL_ID,&id);
        if(!e && id==0)break;
        Delay_Ms(1);
    }
    /* Always release reset even when the first wait failed. */
    e=VL53L0X_WrByte(&device,VL53L0X_REG_SOFT_RESET_GO2_SOFT_RESET_N,1);
    if(e)return e;
    if(i==100)return VL53L0X_ERROR_TIME_OUT;
    for(i=0;i<100;i++){
        e=VL53L0X_RdByte(&device,VL53L0X_REG_IDENTIFICATION_MODEL_ID,&id);
        if(!e && id==0xEE)return VL53L0X_ERROR_NONE;
        Delay_Ms(1);
    }
    return VL53L0X_ERROR_TIME_OUT;
}
static VL53L0X_Error initialize(void)
{
    VL53L0X_Error e;
    uint8_t id=0, vhv, phase, aperture;
    uint32_t spads;
    device.I2cDevAddr=0x52;
    range_stage=1;
    e=VL53L0X_RdByte(&device,0xC0,&id); range_model_id=id;
    if(e || id!=0xEE) return e ? e : VL53L0X_ERROR_NOT_SUPPORTED;
    range_stage=9; e=reset_sensor(); if(e)return e;
    range_stage=2; e=VL53L0X_DataInit(&device); if(e)return e;
    range_stage=3; e=VL53L0X_StaticInit(&device); if(e)return e;
    range_stage=4; e=VL53L0X_PerformRefSpadManagement(&device,&spads,&aperture); if(e)return e;
    range_stage=5; e=VL53L0X_PerformRefCalibration(&device,&vhv,&phase); if(e)return e;
    range_stage=6; e=VL53L0X_SetDeviceMode(&device,VL53L0X_DEVICEMODE_SINGLE_RANGING); if(e)return e;
    range_stage=7; e=VL53L0X_SetMeasurementTimingBudgetMicroSeconds(&device,33000); if(e)return e;
    range_stage=8; return VL53L0X_ERROR_NONE;
}
int main(void)
{
    GPIO_InitTypeDef gpio={0};
    VL53L0X_RangingMeasurementData_t measurement;
    uint32_t index;
    NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);
    SystemCoreClockUpdate();Delay_Init();USART_Printf_Init(115200);
    range_bus_init();
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOD,ENABLE);
    gpio.GPIO_Pin=GPIO_Pin_0;gpio.GPIO_Mode=GPIO_Mode_Out_PP;gpio.GPIO_Speed=GPIO_Speed_2MHz;
    GPIO_Init(GPIOD,&gpio);
    Delay_Ms(100);
    range_init_error=initialize();
    printf("ZHIXING RAW RANGE v2 init=%ld stage=%lu\r\n",(long)range_init_error,(unsigned long)range_stage);
    for(;;){
        memset(&measurement,0,sizeof(measurement));
        measurement.RangeStatus=255;
        range_error=range_init_error ? range_init_error : VL53L0X_PerformSingleRangingMeasurement(&device,&measurement);
        range_status=measurement.RangeStatus;
        range_mm=range_error ? 0xFFFFFFFFu : measurement.RangeMilliMeter;
        ++range_rounds;
        if(!range_error && !range_status)++range_valid_count;
        index=range_history_count%32;
        range_history[index].round=range_rounds;
        range_history[index].mm=range_mm;
        range_history[index].status=range_status;
        range_history[index].error=range_error;
        ++range_history_count;
        printf("RANGE round=%lu mm=%lu status=%lu error=%ld\r\n",(unsigned long)range_rounds,(unsigned long)range_mm,(unsigned long)range_status,(long)range_error);
        if(range_rounds&1)GPIO_SetBits(GPIOD,GPIO_Pin_0);else GPIO_ResetBits(GPIOD,GPIO_Pin_0);
        Delay_Ms(200);
    }
}
