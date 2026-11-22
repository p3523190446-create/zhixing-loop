/* CH32 PB6/PB7 open-drain port; single-threaded, bounded clock stretching. */
#include "debug.h"
#include "vl53l0x_platform.h"
#define SCL GPIO_Pin_6
#define SDA GPIO_Pin_7
static uint8_t bus_error; /* 1=SCL stuck, 2=SDA busy, 3=NACK */

static void sda(uint8_t high)
{
    if (high) GPIO_SetBits(GPIOB, SDA); else GPIO_ResetBits(GPIOB, SDA);
    Delay_Us(5);
}
static void scl_low(void)
{
    GPIO_ResetBits(GPIOB, SCL);
    Delay_Us(5);
}
static uint8_t scl_high(void)
{
    unsigned wait;
    GPIO_SetBits(GPIOB, SCL);
    for (wait = 0; wait < 100; ++wait) {
        if (GPIO_ReadInputDataBit(GPIOB, SCL)) { Delay_Us(5); return 1; }
        Delay_Us(5);
    }
    bus_error = 1;
    return 0;
}
static uint8_t start(void)
{
    sda(1);
    if (!scl_high()) return 0;
    if (!GPIO_ReadInputDataBit(GPIOB, SDA)) { bus_error = 2; return 0; }
    sda(0);
    scl_low();
    return 1;
}
static void stop(void)
{
    scl_low();
    sda(0);
    scl_high();
    sda(1);
    GPIO_SetBits(GPIOB, SCL | SDA);
}
static uint8_t write_byte(uint8_t byte)
{
    uint8_t mask;
    for (mask = 0x80; mask; mask >>= 1) {
        sda((byte & mask) != 0);
        if (!scl_high()) return 0;
        scl_low();
    }
    sda(1);
    if (!scl_high()) return 0;
    if (GPIO_ReadInputDataBit(GPIOB, SDA)) bus_error = 3;
    scl_low();
    return bus_error == 0;
}
static uint8_t read_byte(uint8_t *value, uint8_t acknowledge)
{
    uint8_t bit, byte = 0;
    sda(1);
    for (bit = 0; bit < 8; ++bit) {
        if (!scl_high()) return 0;
        byte = (uint8_t)((byte << 1) | GPIO_ReadInputDataBit(GPIOB, SDA));
        scl_low();
    }
    sda(!acknowledge);
    if (!scl_high()) return 0;
    scl_low();
    sda(1);
    *value = byte;
    return 1;
}

void range_bus_init(void){
 GPIO_InitTypeDef g={0};RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOB,ENABLE);
 GPIO_SetBits(GPIOB,SCL|SDA);g.GPIO_Pin=SCL|SDA;g.GPIO_Mode=GPIO_Mode_Out_OD;g.GPIO_Speed=GPIO_Speed_2MHz;GPIO_Init(GPIOB,&g);
}
/* NXP UM10204 bus clear: release SDA, at most nine clocks, then STOP.
 * A hard low cannot be repaired in software; return and retry later. */
VL53L0X_Error range_bus_recover(void)
{
 unsigned i;bus_error=0;sda(1);
 if(!scl_high())goto failed;
 for(i=0;i<9 && !GPIO_ReadInputDataBit(GPIOB,SDA);i++){
  scl_low();if(!scl_high())goto failed;
 }
 stop();
 if(!GPIO_ReadInputDataBit(GPIOB,SCL) || !GPIO_ReadInputDataBit(GPIOB,SDA))goto failed;
 return VL53L0X_ERROR_NONE;
failed:
 GPIO_SetBits(GPIOB,SCL|SDA);
 return VL53L0X_ERROR_CONTROL_INTERFACE;
}
VL53L0X_Error VL53L0X_LockSequenceAccess(VL53L0X_DEV d){(void)d;return 0;}
VL53L0X_Error VL53L0X_UnlockSequenceAccess(VL53L0X_DEV d){(void)d;return 0;}
VL53L0X_Error VL53L0X_PollingDelay(VL53L0X_DEV d){(void)d;Delay_Ms(1);return 0;}
VL53L0X_Error VL53L0X_WriteMulti(VL53L0X_DEV d,uint8_t r,uint8_t *v,uint32_t n){
 uint32_t i;bus_error=0;
 if(!start()||!write_byte(d->I2cDevAddr)||!write_byte(r))goto done;
 for(i=0;i<n;i++)if(!write_byte(v[i]))break;
done:stop();return bus_error?VL53L0X_ERROR_CONTROL_INTERFACE:0;
}
VL53L0X_Error VL53L0X_ReadMulti(VL53L0X_DEV d,uint8_t r,uint8_t *v,uint32_t n){
 uint32_t i;bus_error=0;
 if(!start()||!write_byte(d->I2cDevAddr)||!write_byte(r)||!start()||!write_byte(d->I2cDevAddr|1))goto done;
 for(i=0;i<n;i++)if(!read_byte(&v[i],i+1<n))break;
done:stop();return bus_error?VL53L0X_ERROR_CONTROL_INTERFACE:0;
}
VL53L0X_Error VL53L0X_WrByte(VL53L0X_DEV d,uint8_t r,uint8_t v){return VL53L0X_WriteMulti(d,r,&v,1);}
VL53L0X_Error VL53L0X_WrWord(VL53L0X_DEV d,uint8_t r,uint16_t v){uint8_t b[2]={(uint8_t)(v>>8),(uint8_t)v};return VL53L0X_WriteMulti(d,r,b,2);}
VL53L0X_Error VL53L0X_WrDWord(VL53L0X_DEV d,uint8_t r,uint32_t v){uint8_t b[4]={(uint8_t)(v>>24),(uint8_t)(v>>16),(uint8_t)(v>>8),(uint8_t)v};return VL53L0X_WriteMulti(d,r,b,4);}
VL53L0X_Error VL53L0X_RdByte(VL53L0X_DEV d,uint8_t r,uint8_t *v){return VL53L0X_ReadMulti(d,r,v,1);}
VL53L0X_Error VL53L0X_RdWord(VL53L0X_DEV d,uint8_t r,uint16_t *v){uint8_t b[2]={0};VL53L0X_Error e=VL53L0X_ReadMulti(d,r,b,2);if(!e)*v=((uint16_t)b[0]<<8)|b[1];return e;}
VL53L0X_Error VL53L0X_RdDWord(VL53L0X_DEV d,uint8_t r,uint32_t *v){uint8_t b[4]={0};VL53L0X_Error e=VL53L0X_ReadMulti(d,r,b,4);if(!e)*v=((uint32_t)b[0]<<24)|((uint32_t)b[1]<<16)|((uint32_t)b[2]<<8)|b[3];return e;}
VL53L0X_Error VL53L0X_UpdateByte(VL53L0X_DEV d,uint8_t r,uint8_t a,uint8_t o){uint8_t v=0;VL53L0X_Error e=VL53L0X_RdByte(d,r,&v);if(e)return e;return VL53L0X_WrByte(d,r,(v&a)|o);}
