#include "debug.h"
#include "servo_probe.h"
volatile uint32_t servo_probe_ready,servo_probe_active,servo_probe_pulse_us;
volatile uint32_t servo_probe_starts,servo_probe_stops,servo_probe_timer_hz;
static volatile uint32_t started_ms,pattern;
void servo_probe_init(void)
{
    GPIO_InitTypeDef gpio={0};TIM_TimeBaseInitTypeDef timer={0};
    TIM_OCInitTypeDef compare={0};RCC_ClocksTypeDef clocks;uint32_t clock;
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA|RCC_APB2Periph_TIM1,ENABLE);
    RCC_GetClocksFreq(&clocks);clock=clocks.PCLK2_Frequency;
    if(clocks.PCLK2_Frequency!=clocks.HCLK_Frequency)clock*=2u;
    TIM_Cmd(TIM1,DISABLE);TIM_CtrlPWMOutputs(TIM1,DISABLE);
    GPIO_ResetBits(GPIOA,GPIO_Pin_8);
    gpio.GPIO_Pin=GPIO_Pin_8;gpio.GPIO_Mode=GPIO_Mode_AF_PP;gpio.GPIO_Speed=GPIO_Speed_2MHz;
    GPIO_Init(GPIOA,&gpio);
    timer.TIM_Prescaler=(uint16_t)(clock/1000000u-1u);timer.TIM_Period=19999u;
    timer.TIM_CounterMode=TIM_CounterMode_Up;timer.TIM_ClockDivision=TIM_CKD_DIV1;
    TIM_TimeBaseInit(TIM1,&timer);
    compare.TIM_OCMode=TIM_OCMode_PWM1;compare.TIM_OutputState=TIM_OutputState_Enable;
    compare.TIM_Pulse=0;compare.TIM_OCPolarity=TIM_OCPolarity_High;
    TIM_OC1Init(TIM1,&compare);TIM_OC1PreloadConfig(TIM1,TIM_OCPreload_Enable);
    TIM_ARRPreloadConfig(TIM1,ENABLE);TIM_GenerateEvent(TIM1,TIM_EventSource_Update);
    servo_probe_timer_hz=clock/(timer.TIM_Prescaler+1u);
    TIM_CtrlPWMOutputs(TIM1,ENABLE);TIM_Cmd(TIM1,ENABLE);
    servo_probe_ready=servo_probe_timer_hz==1000000u;
    /* CCR=0 at boot; no movement command until explicit serial request. */
}
int servo_probe_start(uint32_t now,unsigned wiggle)
{
    int result=0;
    __disable_irq();
    if(servo_probe_ready && !servo_probe_active && wiggle<=2u){
        started_ms=now;pattern=wiggle;servo_probe_active=1;
        servo_probe_pulse_us=1500u;TIM_SetCompare1(TIM1,1500u);
        ++servo_probe_starts;result=1;
    }
    __enable_irq();return result;
}
void servo_probe_stop(void)
{
    if(servo_probe_active)++servo_probe_stops;
    servo_probe_active=0;servo_probe_pulse_us=0;TIM_SetCompare1(TIM1,0);
}
void servo_probe_tick(uint32_t now)
{
    uint16_t pulse;
    if(!servo_probe_ready || !servo_probe_active)return;
    pulse=servo_probe_pattern((uint32_t)(now-started_ms),pattern);
    if(!pulse){servo_probe_stop();return;}
    if(pulse!=servo_probe_pulse_us){servo_probe_pulse_us=pulse;TIM_SetCompare1(TIM1,pulse);}
}
