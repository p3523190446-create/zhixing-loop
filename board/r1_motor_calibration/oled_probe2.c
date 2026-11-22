/* First display's isolated software I2C: PB10 SCL / PB11 SDA.
 * Probe only: no panel initialization, no change to the PB6/PB7 ToF bus.
 * The display module must provide pullups to the shared 3.3V supply. */
#include "debug.h"
#include "oled_probe2.h"
#define SCL GPIO_Pin_10
#define SDA GPIO_Pin_11
volatile uint32_t oled2_scan_count, oled2_ack_3c, oled2_ack_3d, oled2_bus_error, oled2_idle_lines;
static uint32_t last_scan;
static uint8_t scanned;
static void data(uint8_t high)
{
    if(high)GPIO_SetBits(GPIOB,SDA);else GPIO_ResetBits(GPIOB,SDA);
    Delay_Us(5);
}
static void clock_low(void){GPIO_ResetBits(GPIOB,SCL);Delay_Us(5);}
static uint8_t clock_high(void)
{
    unsigned i;
    GPIO_SetBits(GPIOB,SCL);
    for(i=0;i<20;i++){
        if(GPIO_ReadInputDataBit(GPIOB,SCL)){Delay_Us(5);return 1;}
        Delay_Us(5);
    }
    oled2_bus_error=1;return 0;
}
static uint8_t probe(uint8_t address)
{
    unsigned mask;uint8_t ack=0,byte=(uint8_t)(address<<1);
    data(1);
    if(!clock_high())goto done;
    if(!GPIO_ReadInputDataBit(GPIOB,SDA)){oled2_bus_error=2;goto done;}
    data(0);clock_low();
    for(mask=128;mask;mask>>=1){
        data((byte&mask)!=0);
        if(!clock_high())goto done;
        clock_low();
    }
    data(1);
    if(!clock_high())goto done;
    ack=!GPIO_ReadInputDataBit(GPIOB,SDA);
done:
    clock_low();data(0);clock_high();data(1);
    GPIO_SetBits(GPIOB,SCL|SDA);
    return ack;
}
static uint8_t write_byte(uint8_t byte)
{
    unsigned mask;uint8_t ack;
    for(mask=128;mask;mask>>=1){
        data((byte&mask)!=0);if(!clock_high())return 0;clock_low();
    }
    data(1);if(!clock_high())return 0;
    ack=!GPIO_ReadInputDataBit(GPIOB,SDA);clock_low();
    if(!ack)oled2_bus_error=3;
    return ack;
}
uint8_t oled2_bus_write(uint8_t address,uint8_t control,const uint8_t *bytes,unsigned count)
{
    unsigned i;uint8_t ok=0;
    oled2_bus_error=0;data(1);
    if(!clock_high())goto done;
    if(!GPIO_ReadInputDataBit(GPIOB,SDA)){oled2_bus_error=2;goto done;}
    data(0);clock_low();
    if(!write_byte((uint8_t)(address<<1)) || !write_byte(control))goto done;
    for(i=0;i<count;i++)if(!write_byte(bytes[i]))goto done;
    ok=1;
done:
    clock_low();data(0);if(!clock_high())ok=0;data(1);
    return ok;
}
void oled_probe2_init(void)
{
    GPIO_InitTypeDef gpio={0};
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOB,ENABLE);
    GPIO_SetBits(GPIOB,SCL|SDA);
    gpio.GPIO_Pin=SCL|SDA;gpio.GPIO_Mode=GPIO_Mode_Out_OD;gpio.GPIO_Speed=GPIO_Speed_2MHz;
    GPIO_Init(GPIOB,&gpio);
}
void oled_probe2_poll(uint32_t now)
{
    if(scanned && (uint32_t)(now-last_scan)<2000)return;
    scanned=1;last_scan=now;oled2_bus_error=0;
    oled2_idle_lines=(GPIO_ReadInputDataBit(GPIOB,SCL)?1u:0u)|(GPIO_ReadInputDataBit(GPIOB,SDA)?2u:0u);
    oled2_ack_3c=probe(0x3c);
    oled2_ack_3d=probe(0x3d);
    ++oled2_scan_count;
}
