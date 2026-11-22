/* USBFS diagnostic only. No motor/servo commands or UART bridge.
 * Vendor USB source remains licensed for WCH microcontrollers only. */
#include "UART.h"
extern void native_usb_poll(void);
int main(void)
{
    GPIO_InitTypeDef pins={0};
    NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);
    SystemCoreClockUpdate();Delay_Init();
    /* Known active-low lamps/buzzer OFF; both servo signal pins held LOW.
     * Motor battery and both servo supplies must remain physically disconnected. */
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA|RCC_APB2Periph_GPIOB|RCC_APB2Periph_GPIOD,ENABLE);
    GPIO_SetBits(GPIOD,GPIO_Pin_0|GPIO_Pin_1|GPIO_Pin_2|GPIO_Pin_3);
    pins.GPIO_Pin=GPIO_Pin_0|GPIO_Pin_1|GPIO_Pin_2|GPIO_Pin_3;
    pins.GPIO_Mode=GPIO_Mode_Out_PP;pins.GPIO_Speed=GPIO_Speed_2MHz;GPIO_Init(GPIOD,&pins);
    GPIO_ResetBits(GPIOA,GPIO_Pin_8);pins.GPIO_Pin=GPIO_Pin_8;GPIO_Init(GPIOA,&pins);
    GPIO_ResetBits(GPIOB,GPIO_Pin_0);pins.GPIO_Pin=GPIO_Pin_0;GPIO_Init(GPIOB,&pins);
    UART2_ParaInit(1); /* Software buffers only: does not configure USART2 pins. */
    USBFS_RCC_Init();USBFS_Device_Init(ENABLE);
    for(;;)native_usb_poll();
}
