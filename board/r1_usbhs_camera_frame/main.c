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

static uint8_t image[16384],packet[512],probe[34];
static uint32_t get32(const uint8_t *p){return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(uint8_t *p,uint32_t v){p[0]=v;p[1]=v>>8;p[2]=v>>16;p[3]=v>>24;}
static uint8_t control(uint8_t ep0,uint8_t direction,uint8_t request,uint16_t selector,uint8_t *data,uint16_t n,uint16_t *got)
{
 uint8_t setup[8]={direction,request,0,(uint8_t)selector,1,0,(uint8_t)n,(uint8_t)(n>>8)};
 memcpy(USBHS_TX_Buf,setup,8);return USBHSH_CtrlTransfer(ep0,data,got);
}
static void one_frame(uint8_t ep0,uint8_t configuration)
{
 uint8_t result,toggle=0,flags=0,bad=0;uint16_t got=0,n=0,probe_len=26;
 uint32_t max_payload,used=0,length=0,packets=0,errors=0;int fid=-1;
 result=USBHSH_SetUsbConfig(ep0,configuration);printf("UVC_STAGE,SET_CONFIG,%u\n",result);if(result)return;
 Delay_Ms(100);
 result=control(ep0,0xa1,0x85,1,probe,2,&got);
 if(!result&&got==2){uint16_t reported=probe[0]|probe[1]<<8;if(reported>=26&&reported<=34)probe_len=reported;}
 memset(probe,0,sizeof(probe));probe[0]=1;probe[2]=1;probe[3]=10;
 put32(probe+4,2000000u);put32(probe+18,38989u);put32(probe+22,512u);
 result=control(ep0,0x21,1,1,probe,probe_len,&got);printf("UVC_STAGE,SET_PROBE,%u,%u\n",result,probe_len);if(result)return;
 result=control(ep0,0xa1,0x81,1,probe,probe_len,&got);printf("UVC_STAGE,GET_PROBE,%u,%u\n",result,got);if(result||got<26)return;
 hex_dump("PROBE",probe,got);max_payload=get32(probe+22);
 if(probe[2]!=1||probe[3]!=10||max_payload<512||max_payload>1048576){printf("UVC_RESULT,NEGOTIATION_REJECTED\n");return;}
 result=control(ep0,0x21,1,2,probe,probe_len,&got);printf("UVC_STAGE,COMMIT,%u,%lu\n",result,(unsigned long)max_payload);if(result)return;
 for(unsigned attempt=0;attempt<200000;attempt++){
  if(!(USBHSH->MIS_ST&USBHS_UMS_DEV_ATTACH)){printf("UVC_RESULT,DETACHED\n");return;}
  result=USBHSH_GetEndpData(5,&toggle,packet,&n);
  if(result){errors++;Delay_Us(50);continue;}
  packets++;if(n>sizeof(packet)){printf("UVC_RESULT,PACKET_OVERFLOW\n");return;}
  unsigned skip=0;
  if(used==0 && n){
   skip=packet[0];if(n<2||skip<2||skip>n){bad=1;flags=0;}
   else {flags=packet[1];if((flags&1)!=fid){fid=flags&1;length=0;bad=0;}if(flags&0x40)bad=1;}
  }
  if(!bad&&n>=skip){unsigned bytes=n-skip;if(length+bytes<=sizeof(image)){memcpy(image+length,packet+skip,bytes);length+=bytes;}else bad=1;}
  used+=n;
  if(n<512||used>=max_payload){
   used=0;
   if((flags&2)&&!bad&&length>=4&&image[0]==0xff&&image[1]==0xd8&&image[length-2]==0xff&&image[length-1]==0xd9){
    printf("UVC_FRAME,160,120,%lu,%lu,%lu\n",(unsigned long)length,(unsigned long)packets,(unsigned long)errors);
    hex_dump("JPEG",image,length);printf("UVC_RESULT,FRAME_READ\n");return;
   }
  }
 }
 printf("UVC_RESULT,TIMEOUT,%lu,%lu,%lu\n",(unsigned long)packets,(unsigned long)errors,(unsigned long)length);
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
    one_frame(ep0,config[5]);
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
    printf("USBHS_CAMERA_FRAME,1,PB6_PB7_SENSOR_LEADS_MUST_BE_REMOVED\n");
    USBHS_RCC_Init();USBHS_Host_Init(ENABLE);
    while(1){
        if(USBHSH->MIS_ST&USBHS_UMS_DEV_ATTACH){
            if(!attempted){attempted=1;enumerate();}
        }else if(attempted){attempted=0;printf("USBHS_DETACHED\n");}
        Delay_Ms(10);
        if(++wait==100){wait=0;printf("USBHS_WAIT,%u,%u\n",attempted,(USBHSH->MIS_ST&USBHS_UMS_DEV_ATTACH)!=0);}
    }
}
