/* Isolated USBHS descriptor probe. No video streaming, USBFS, sensor polling,
 * servo PWM, driver UART, motor command, or persistent writes.
 * PB6/PB7 sensor leads MUST be disconnected before hardware use. */
#include "usb_host_config.h"
static uint8_t config[4096] __attribute__((aligned(4)));
static uint8_t device[18] __attribute__((aligned(4)));
static void hex_dump(const char *name,const uint8_t *p,unsigned length)
{
    unsigned i;
    for(i=0;i<length;i++){
        if(!(i%16u))printf("USBHS_BYTES,%s,%u,",name,i);
        printf("%02X",p[i]);
        if(i%16u==15u || i+1u==length)printf("\n");
    }
}
static void enumerate(void)
{
    uint8_t speed=USB_SPEED_CHECK_ERR,ep0=8,result;uint16_t count=0;
    Delay_Ms(100);USBHSH_ResetRootHubPort(0);
    result=USBHSH_EnableRootHubPort(&speed);
    printf("USBHS_STAGE,ENABLE,%u,%u\n",result,speed);
    if(result!=ERR_SUCCESS)return;
    USBHSH_SetSelfAddr(0);USBHSH_SetSelfSpeed(speed);Delay_Ms(20);
    result=USBHSH_GetDeviceDescr(&ep0,device);
    printf("USBHS_STAGE,DEVICE,%u,%u\n",result,ep0);
    if(result!=ERR_SUCCESS)return;
    hex_dump("DEVICE",device,sizeof(device));
    printf("USBHS_ID,%04X,%04X\n",device[8]|device[9]<<8,device[10]|device[11]<<8);
    if((device[8]|device[9]<<8)!=0x145f || (device[10]|device[11]<<8)!=0x02ec){
        printf("USBHS_RESULT,NOT_TARGET\n");return;
    }
    result=USBHSH_SetUsbAddress(ep0,2);
    printf("USBHS_STAGE,ADDRESS,%u\n",result);
    if(result!=ERR_SUCCESS)return;
    USBHSH_SetSelfAddr(2);Delay_Ms(10);
    result=USBHSH_GetConfigDescr(ep0,config,sizeof(config),&count);
    printf("USBHS_STAGE,CONFIG,%u,%u\n",result,count);
    if(result!=ERR_SUCCESS || count>sizeof(config))return;
    hex_dump("CONFIG",config,count);
    /* Read descriptors only. Do not commit UVC settings or start stream. */
    printf("USBHS_RESULT,DESCRIPTORS_READ_NO_VIDEO\n");
}
int main(void)
{
    GPIO_InitTypeDef gpio={0};uint8_t attempted=0;unsigned wait=0;
    SystemCoreClockUpdate();Delay_Init();
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA|RCC_APB2Periph_GPIOB,ENABLE);
    GPIO_ResetBits(GPIOA,GPIO_Pin_8);GPIO_ResetBits(GPIOB,GPIO_Pin_0);
    gpio.GPIO_Pin=GPIO_Pin_8;gpio.GPIO_Mode=GPIO_Mode_Out_PP;gpio.GPIO_Speed=GPIO_Speed_2MHz;
    GPIO_Init(GPIOA,&gpio);gpio.GPIO_Pin=GPIO_Pin_0;GPIO_Init(GPIOB,&gpio);
    USART_Printf_Init(115200);
    printf("USBHS_CAMERA_PROBE,1,PB6_PB7_SENSOR_LEADS_MUST_BE_REMOVED\n");
    USBHS_RCC_Init();USBHS_Host_Init(ENABLE);
    while(1){
        if(USBHSH->MIS_ST&USBHS_UMS_DEV_ATTACH){
            if(!attempted){attempted=1;enumerate();}
        }else if(attempted){attempted=0;printf("USBHS_DETACHED\n");}
        Delay_Ms(10);
        if(++wait==100){wait=0;printf("USBHS_WAIT,%u,%u\n",attempted,(USBHSH->MIS_ST&USBHS_UMS_DEV_ATTACH)!=0);}
    }
}
