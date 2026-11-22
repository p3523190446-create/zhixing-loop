#include "debug.h"

/* Standard R1: wire J3 LED1 to J4 PD0, LED2 to PD1 before visual test.
 * LEDs are not directly connected to these GPIOs on the PCB.
 * Only GPIO/USART are enabled; no sensor or motor is driven.
 */
volatile uint32_t bringup_ticks = 0;
volatile uint32_t bringup_chip_id = 0;

int main(void)
{
    GPIO_InitTypeDef gpio = {0};
    NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);
    SystemCoreClockUpdate();
    Delay_Init();
    USART_Printf_Init(115200);
    bringup_chip_id = DBGMCU_GetCHIPID();
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOD, ENABLE);
    gpio.GPIO_Pin = GPIO_Pin_0 | GPIO_Pin_1;
    gpio.GPIO_Mode = GPIO_Mode_Out_PP;
    gpio.GPIO_Speed = GPIO_Speed_2MHz;
    GPIO_Init(GPIOD, &gpio);
    GPIO_ResetBits(GPIOD, GPIO_Pin_0 | GPIO_Pin_1);
    printf("ZHIXING R1 BRINGUP v1 clk=%lu chip=%08lx\r\n",
           (unsigned long)SystemCoreClock, (unsigned long)bringup_chip_id);
    while (1) {
        GPIO_SetBits(GPIOD, GPIO_Pin_0);
        GPIO_ResetBits(GPIOD, GPIO_Pin_1);
        Delay_Ms(500);
        GPIO_ResetBits(GPIOD, GPIO_Pin_0);
        GPIO_SetBits(GPIOD, GPIO_Pin_1);
        Delay_Ms(500);
        ++bringup_ticks;
        printf("R1 alive %lu\r\n", (unsigned long)bringup_ticks);
    }
}
