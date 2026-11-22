#include "debug.h"
#include "servo_probe.h"
static volatile gimbal_snapshot_t state;
static volatile uint32_t start_ms;

static void apply(gimbal_pulses_t p)
{
    TIM_SetCompare1(TIM1,p.yaw);TIM_SetCompare3(TIM3,p.pitch);
    state.yaw_us=p.yaw;state.pitch_us=p.pitch;
}
void servo_probe_init(void)
{
    GPIO_InitTypeDef gpio={0};TIM_TimeBaseInitTypeDef timer={0};
    TIM_OCInitTypeDef compare={0};RCC_ClocksTypeDef clocks;
    uint32_t yaw_clock,pitch_clock;
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA|RCC_APB2Periph_GPIOB|RCC_APB2Periph_AFIO|RCC_APB2Periph_TIM1,ENABLE);
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM3,ENABLE);
    RCC_GetClocksFreq(&clocks);yaw_clock=clocks.PCLK2_Frequency;pitch_clock=clocks.PCLK1_Frequency;
    if(clocks.PCLK2_Frequency!=clocks.HCLK_Frequency)yaw_clock*=2u;
    if(clocks.PCLK1_Frequency!=clocks.HCLK_Frequency)pitch_clock*=2u;
    /* Keep PB0 as the default TIM3_CH3. USART3 remap is a separate AFIO field. */
    GPIO_PinRemapConfig(GPIO_FullRemap_TIM3,DISABLE);
    TIM_Cmd(TIM1,DISABLE);TIM_CtrlPWMOutputs(TIM1,DISABLE);TIM_Cmd(TIM3,DISABLE);
    GPIO_ResetBits(GPIOA,GPIO_Pin_8);GPIO_ResetBits(GPIOB,GPIO_Pin_0);
    gpio.GPIO_Pin=GPIO_Pin_8;gpio.GPIO_Mode=GPIO_Mode_AF_PP;gpio.GPIO_Speed=GPIO_Speed_2MHz;
    GPIO_Init(GPIOA,&gpio);gpio.GPIO_Pin=GPIO_Pin_0;GPIO_Init(GPIOB,&gpio);
    timer.TIM_Prescaler=(uint16_t)(yaw_clock/1000000u-1u);timer.TIM_Period=19999u;
    timer.TIM_CounterMode=TIM_CounterMode_Up;timer.TIM_ClockDivision=TIM_CKD_DIV1;
    TIM_TimeBaseInit(TIM1,&timer);state.yaw_hz=yaw_clock/(timer.TIM_Prescaler+1u);
    timer.TIM_Prescaler=(uint16_t)(pitch_clock/1000000u-1u);
    TIM_TimeBaseInit(TIM3,&timer);state.pitch_hz=pitch_clock/(timer.TIM_Prescaler+1u);
    compare.TIM_OCMode=TIM_OCMode_PWM1;compare.TIM_OutputState=TIM_OutputState_Enable;
    compare.TIM_Pulse=0;compare.TIM_OCPolarity=TIM_OCPolarity_High;
    TIM_OC1Init(TIM1,&compare);TIM_OC3Init(TIM3,&compare);
    TIM_OC1PreloadConfig(TIM1,TIM_OCPreload_Enable);TIM_OC3PreloadConfig(TIM3,TIM_OCPreload_Enable);
    TIM_ARRPreloadConfig(TIM1,ENABLE);TIM_ARRPreloadConfig(TIM3,ENABLE);
    TIM_GenerateEvent(TIM1,TIM_EventSource_Update);TIM_GenerateEvent(TIM3,TIM_EventSource_Update);
    TIM_CtrlPWMOutputs(TIM1,ENABLE);TIM_Cmd(TIM1,ENABLE);TIM_Cmd(TIM3,ENABLE);
    state.ready=state.yaw_hz==1000000u && state.pitch_hz==1000000u;
    /* Both channels boot at zero; no automatic centering on restart. */
}
int servo_probe_start(uint32_t now,unsigned mode)
{
    int result=0;__disable_irq();
    if(state.ready && !state.active && mode>=1u && mode<=3u){
        start_ms=now;state.mode=mode;state.active=1;
        apply(gimbal_pattern(0,mode));++state.starts;result=1;
    }
    __enable_irq();return result;
}
static void stop_locked(void)
{
    gimbal_pulses_t p={0,0};
    if(state.active)++state.stops;
    state.active=0;apply(p);
}
void servo_probe_stop(void)
{
    __disable_irq();stop_locked();__enable_irq();
}
void servo_probe_tick(uint32_t now)
{
    gimbal_pulses_t p;
    if(!state.ready || !state.active)return;
    p=gimbal_pattern((uint32_t)(now-start_ms),state.mode);
    if(!p.yaw && !p.pitch){stop_locked();return;}
    if(p.yaw!=state.yaw_us || p.pitch!=state.pitch_us)apply(p);
}
void servo_probe_snapshot(gimbal_snapshot_t *out)
{
    __disable_irq();*out=state;__enable_irq();
}
