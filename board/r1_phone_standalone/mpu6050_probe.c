/* Independent, bounded software I2C. PD6=SCL, PD7=SDA, AD0 high=0x69.
 * Static telemetry only; no actuator, calibration, EEPROM or Flash calls. */
#include "debug.h"
#include "mpu6050_probe.h"
#include "imu_observer.h"
#include "imu_reference.h"
#include "imu_identity_policy.h"
#include <stdio.h>
#include <string.h>
#define SCL GPIO_Pin_6
#define SDA GPIO_Pin_7
#define ADDRESS 0x69u
static uint8_t bus_error,ready,identity,last_error;
static uint8_t compat_trial=IMU_AUTO_COMPAT_ID72;
static unsigned bus_delay=2;
static uint32_t last_attempt,last_sample,samples,errors;
static imu_observer_t observer;
static long milli(float x){return (long)(x*1000+(x>=0?.5f:-.5f));}
static int16_t raw[7]; /* ax,ay,az,temp,gx,gy,gz */

static void sda(unsigned high)
{
    if(high)GPIO_SetBits(GPIOD,SDA);else GPIO_ResetBits(GPIOD,SDA);
    Delay_Us(bus_delay);
}
static void scl_low(void){GPIO_ResetBits(GPIOD,SCL);Delay_Us(bus_delay);}
static int scl_high(void)
{
    unsigned i;GPIO_SetBits(GPIOD,SCL);
    for(i=0;i<25;i++){
        if(GPIO_ReadInputDataBit(GPIOD,SCL)){Delay_Us(bus_delay);return 1;}
        Delay_Us(bus_delay);
    }
    bus_error=1;return 0;
}
static int start(void)
{
    sda(1);if(!scl_high())return 0;
    if(!GPIO_ReadInputDataBit(GPIOD,SDA)){bus_error=2;return 0;}
    sda(0);scl_low();return 1;
}
static void stop(void)
{
    scl_low();sda(0);(void)scl_high();sda(1);GPIO_SetBits(GPIOD,SCL|SDA);
}
static int write_byte(uint8_t value)
{
    unsigned mask;
    for(mask=0x80;mask;mask>>=1){
        sda(value&mask);if(!scl_high())return 0;scl_low();
    }
    sda(1);if(!scl_high())return 0;
    if(GPIO_ReadInputDataBit(GPIOD,SDA))bus_error=3;
    scl_low();return !bus_error;
}
static int read_byte(uint8_t *value,unsigned ack)
{
    unsigned i;uint8_t v=0;sda(1);
    for(i=0;i<8;i++){
        if(!scl_high())return 0;
        v=(uint8_t)((v<<1)|GPIO_ReadInputDataBit(GPIOD,SDA));scl_low();
    }
    sda(!ack);if(!scl_high())return 0;scl_low();sda(1);*value=v;return 1;
}
static int read_regs(uint8_t reg,uint8_t *out,unsigned count)
{
    unsigned i;int ok=0;bus_error=0;
    if(!start()||!write_byte(ADDRESS<<1)||!write_byte(reg)||!start()||!write_byte((ADDRESS<<1)|1))goto done;
    for(i=0;i<count;i++)if(!read_byte(out+i,i+1<count))goto done;
    ok=1;
done:stop();return ok&&!bus_error;
}
static int write_reg(uint8_t reg,uint8_t value)
{
    int ok;bus_error=0;
    ok=start()&&write_byte(ADDRESS<<1)&&write_byte(reg)&&write_byte(value);
    stop();return ok&&!bus_error;
}
/* Independent STOP/START pointer read, used only for read-only diagnosis. */
static int read_stop(uint8_t reg,uint8_t *value)
{
    int ok;bus_error=0;ok=start()&&write_byte(ADDRESS<<1)&&write_byte(reg);stop();
    if(!ok||bus_error)return 0;
    bus_error=0;ok=start()&&write_byte((ADDRESS<<1)|1)&&read_byte(value,0);stop();
    return ok&&!bus_error;
}
static int configure(void)
{
    uint8_t config[3];
    if(!read_regs(0x75,&identity,1))return 0;
    /* Restore this installed sensor on every boot; all other IDs remain rejected. */
    if(!imu_identity_allowed(identity,compat_trial)){bus_error=4;return 0;}
    /* PLL X gyro, DLPF ~44Hz, sample 50Hz, gyro +/-250dps, accel +/-2g. */
    if(!write_reg(0x6B,0x01)||!write_reg(0x1A,0x06)||!write_reg(0x19,19)||
       !write_reg(0x1B,0)||!write_reg(0x1C,0))return 0;
    if(!read_regs(0x1A,config,3))return 0;
    if(config[0]!=6||config[1]!=0||config[2]!=0){bus_error=5;return 0;}
    return 1;
}
void mpu6050_probe_init(uint32_t now)
{
    GPIO_InitTypeDef gpio={0};RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOD,ENABLE);
    GPIO_SetBits(GPIOD,SCL|SDA);gpio.GPIO_Pin=SCL|SDA;
    gpio.GPIO_Mode=GPIO_Mode_Out_OD;gpio.GPIO_Speed=GPIO_Speed_2MHz;GPIO_Init(GPIOD,&gpio);
    last_attempt=now;imu_observer_init(&observer);
}
void mpu6050_probe_poll(uint32_t now)
{
    uint8_t bytes[14];unsigned i;
    if((uint32_t)(now-last_attempt)<(ready?50u:1000u))return;
    last_attempt=now;
    if(!ready){
        if(configure()){ready=1;last_error=0;return;}
    }else if(read_regs(0x3B,bytes,sizeof(bytes))){
        for(i=0;i<7;i++)raw[i]=(int16_t)(((uint16_t)bytes[i*2]<<8)|bytes[i*2+1]);
        last_sample=now;++samples;last_error=0;imu_observer_update(&observer,raw,now);return;
    }
    ++errors;last_error=bus_error?bus_error:6;ready=0;
}
int mpu6050_probe_command(const char *command,uint32_t now,void (*reply)(const char *))
{
    char text[256];uint32_t age=samples?(uint32_t)(now-last_sample):0xFFFFFFFFu;
    unsigned valid=ready&&samples&&age<250u;
    if(!strcmp(command,"MPU_FEATURES_ID"))reply("MPU_FEATURES_ID,IMU_OBSERVER_V1_20HZ\n");
    else if(!strcmp(command,"MPU_FEATURES")){
        uint32_t a=observer.initialized?(uint32_t)(now-observer.now):0xFFFFFFFFu;
        snprintf(text,sizeof(text),"MPU_FEATURES,%lu,%lu,%u,%lu,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%lu,%lu,%lu,%lu,%lu,%lu\n",
          (unsigned long)now,(unsigned long)a,(unsigned)(valid&&imu_observer_valid(&observer,now)),(unsigned long)observer.flags,
          milli(observer.front_up),milli(observer.left_up),milli(observer.yaw_window),milli(observer.gyro_z),
          milli(observer.rms),milli(observer.peak),milli(observer.jerk),(unsigned long)observer.shock_count,
          (unsigned long)observer.tilt_count,(unsigned long)observer.fall_count,(unsigned long)observer.window_ms,
          (unsigned long)observer.count,(unsigned long)IMU_REFERENCE_TAG);reply(text);
    }
    else if(!strcmp(command,"MPU_ID"))reply("MPU_ID,MPU6050_PD6_PD7_ADDR69_V1\n");
    else if(!strcmp(command,"MPU_STATUS")){
        snprintf(text,sizeof(text),"MPU_STATUS,%lu,%u,%u,%u,%u,%u,%u,%lu,%lu,%u,%lu\n",
            (unsigned long)now,(unsigned)ready,valid,ADDRESS,(unsigned)identity,
            (unsigned)GPIO_ReadInputDataBit(GPIOD,SCL),(unsigned)GPIO_ReadInputDataBit(GPIOD,SDA),
            (unsigned long)samples,(unsigned long)errors,(unsigned)last_error,(unsigned long)age);
        reply(text);
    }else if(!strcmp(command,"MPU_RAW")){
        snprintf(text,sizeof(text),"MPU_RAW,%lu,%u,%d,%d,%d,%d,%d,%d,%d\n",
            (unsigned long)age,valid,raw[0],raw[1],raw[2],raw[3],raw[4],raw[5],raw[6]);reply(text);
    }else if(!strcmp(command,"MPU_DIAG")){
        uint8_t fast=0,slow=0,pwr=0,rate=0,config[3]={0};unsigned ok=1;
        ok&=read_regs(0x75,&fast,1);bus_delay=6;ok&=read_stop(0x75,&slow);bus_delay=2;
        ok&=read_regs(0x6B,&pwr,1);ok&=read_regs(0x19,&rate,1);ok&=read_regs(0x1A,config,3);
        snprintf(text,sizeof(text),"MPU_DIAG,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
            ok,(unsigned)fast,(unsigned)slow,(unsigned)pwr,(unsigned)rate,
            (unsigned)config[0],(unsigned)config[1],(unsigned)config[2],(unsigned)compat_trial);reply(text);
    }else if(!strcmp(command,"MPU_COMPAT_ON")){
        if(identity==0x72 && !ready){compat_trial=1;reply("MPU_COMPAT_ON,TRIAL_ID72\n");}
        else reply("MPU_COMPAT_ON,REJECTED\n");
    }else return 0;
    return 1;
}
