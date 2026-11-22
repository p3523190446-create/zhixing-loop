#include "debug.h"
#include "ultrasonic.h"
extern volatile uint32_t tick_ms;
volatile ultra_state_t ultrasonic_state;
volatile uint32_t ultrasonic_timer_hz;
static volatile uint8_t ready;

void EXTI15_10_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
void EXTI15_10_IRQHandler(void)
{
    if(EXTI_GetITStatus(EXTI_Line13)!=RESET){
        uint16_t count=(uint16_t)TIM_GetCounter(TIM4);
        unsigned high=GPIO_ReadInputDataBit(GPIOD,GPIO_Pin_13);
        EXTI_ClearITPendingBit(EXTI_Line13);
        if(ready)ultra_edge(&ultrasonic_state,tick_ms,count,high);
    }
}
void ultrasonic_init(void)
{
    RCC_ClocksTypeDef clocks;
    GPIO_InitTypeDef gpio={0};TIM_TimeBaseInitTypeDef timer={0};
    EXTI_InitTypeDef exti={0};NVIC_InitTypeDef irq={0};
    uint32_t clock;
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOD|RCC_APB2Periph_AFIO,ENABLE);
    GPIO_ResetBits(GPIOD,GPIO_Pin_12);
    gpio.GPIO_Pin=GPIO_Pin_12;gpio.GPIO_Mode=GPIO_Mode_Out_PP;gpio.GPIO_Speed=GPIO_Speed_2MHz;
    GPIO_Init(GPIOD,&gpio);
    gpio.GPIO_Pin=GPIO_Pin_13;gpio.GPIO_Mode=GPIO_Mode_IPD;GPIO_Init(GPIOD,&gpio);
    RCC_GetClocksFreq(&clocks);clock=clocks.PCLK1_Frequency;
    if(clocks.PCLK1_Frequency!=clocks.HCLK_Frequency)clock*=2u;
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM4,ENABLE);
    timer.TIM_Prescaler=(uint16_t)(clock/1000000u-1u);timer.TIM_Period=65535u;
    timer.TIM_CounterMode=TIM_CounterMode_Up;timer.TIM_ClockDivision=TIM_CKD_DIV1;
    TIM_TimeBaseInit(TIM4,&timer);TIM_SetCounter(TIM4,0);
    ultrasonic_timer_hz=clock/(timer.TIM_Prescaler+1u);TIM_Cmd(TIM4,ENABLE);
    /* TIM4 internal clock only: no GPIO remap or PWM channels enabled. */
    GPIO_EXTILineConfig(GPIO_PortSourceGPIOD,GPIO_PinSource13);
    exti.EXTI_Line=EXTI_Line13;exti.EXTI_Mode=EXTI_Mode_Interrupt;
    exti.EXTI_Trigger=EXTI_Trigger_Rising_Falling;exti.EXTI_LineCmd=ENABLE;
    EXTI_ClearITPendingBit(EXTI_Line13);EXTI_Init(&exti);
    irq.NVIC_IRQChannel=EXTI15_10_IRQn;irq.NVIC_IRQChannelPreemptionPriority=1;
    irq.NVIC_IRQChannelSubPriority=0;irq.NVIC_IRQChannelCmd=ENABLE;NVIC_Init(&irq);
    ultrasonic_state.distance_mm=0xffffffffu;
    ultrasonic_state.last_trigger_ms=tick_ms-100u;ready=1;
}
void ultrasonic_tick(uint32_t now)
{
    if(ready)ultra_expire(&ultrasonic_state,now);
}
void ultrasonic_poll(uint32_t now)
{
    int trigger;
    if(!ready || ultrasonic_timer_hz!=1000000u)return;
    /* Mask both writers while arming; pending edges are cleared before a new pulse. */
    __disable_irq();
    if(!ultrasonic_state.phase)EXTI_ClearITPendingBit(EXTI_Line13);
    trigger=ultra_begin(&ultrasonic_state,now,GPIO_ReadInputDataBit(GPIOD,GPIO_Pin_13));
    __enable_irq();
    if(trigger){GPIO_SetBits(GPIOD,GPIO_Pin_12);Delay_Us(12);GPIO_ResetBits(GPIOD,GPIO_Pin_12);}
}
void ultrasonic_snapshot(ultra_state_t *out)
{
    __disable_irq();*out=ultrasonic_state;__enable_irq();
}
