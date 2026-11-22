
#include "usb_host_config.h"
#include "uvc_bridge.h"
/* Single bounded frame. Immutable until RELEASE or 5s without reader progress. */
static uint8_t image[8192],packet[512],probe[34],config[2048],device[18];
static uint8_t enabled,running,ready,toggle,flags,bad;static int fid=-1;
static uint32_t payload_limit,used,length,frame_id,ready_ms,packets,errors,drops,error_code;
static uint32_t get32(const uint8_t *p){return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(uint8_t *p,uint32_t v){p[0]=v;p[1]=v>>8;p[2]=v>>16;p[3]=v>>24;}
static uint8_t control(uint8_t ep0,uint8_t direction,uint8_t request,uint16_t selector,uint8_t *data,uint16_t n,uint16_t *got)
{uint8_t setup[8]={direction,request,0,(uint8_t)selector,1,0,(uint8_t)n,(uint8_t)(n>>8)};memcpy(USBHS_TX_Buf,setup,8);return USBHSH_CtrlTransfer(ep0,data,got);}
void uvc_bridge_stop(void){running=ready=0;length=used=0;fid=-1;if(enabled){USBHS_Host_Init(DISABLE);enabled=0;}}
static int start(void)
{
 uint8_t speed=0,ep0=8,result,format=0,frame=0,video=0;uint16_t count=0,got=0,n=26;
 if(running)return 1;
 uvc_bridge_stop();error_code=0;USBHS_RCC_Init();USBHS_Host_Init(ENABLE);enabled=1;
 /* Attach status settles after enabling the PHY, including a camera which
  * was already plugged in before boot. Bound this wait to half a second. */
 for(unsigned wait=0;wait<50 && !(USBHSH->MIS_ST&USBHS_UMS_DEV_ATTACH);wait++)Delay_Ms(10);
 if(!(USBHSH->MIS_ST&USBHS_UMS_DEV_ATTACH)){error_code=1;return 0;}
 Delay_Ms(100);USBHSH_ResetRootHubPort(0);result=USBHSH_EnableRootHubPort(&speed);
 if(result){error_code=100+result;return 0;}USBHSH_SetSelfAddr(0);USBHSH_SetSelfSpeed(speed);Delay_Ms(20);
 result=USBHSH_GetDeviceDescr(&ep0,device);
 if(result||(device[8]|device[9]<<8)!=0x145f||(device[10]|device[11]<<8)!=0x02ec){error_code=2;return 0;}
 result=USBHSH_SetUsbAddress(ep0,2);if(result){error_code=200+result;return 0;}
 result=USBHSH_GetConfigDescr(ep0,config,sizeof(config),&count);if(result||count>sizeof(config)){error_code=3;return 0;}
 for(unsigned at=0;at<count;){
  unsigned size=config[at];if(size<2||at+size>count){error_code=4;return 0;}uint8_t *d=config+at;
  if(d[1]==4&&size>=9)video=d[2]==1&&d[3]==0&&d[5]==14&&d[6]==2;
  if(video&&d[1]==0x24&&size>=11&&d[2]==6)format=d[3];
  if(video&&d[1]==0x24&&size>=26&&d[2]==7&&(d[5]|d[6]<<8)==160&&(d[7]|d[8]<<8)==120)frame=d[3];
  at+=size;
 }
 if(format!=1||frame!=10){error_code=5;return 0;}
 result=USBHSH_SetUsbConfig(ep0,config[5]);if(result){error_code=300+result;return 0;}Delay_Ms(100);
 result=control(ep0,0xa1,0x85,1,probe,2,&got);if(!result&&got==2){uint16_t size=probe[0]|probe[1]<<8;if(size>=26&&size<=34)n=size;}
 memset(probe,0,sizeof(probe));probe[0]=1;probe[2]=format;probe[3]=frame;put32(probe+4,2000000u);put32(probe+18,38989u);put32(probe+22,512u);
 result=control(ep0,0x21,1,1,probe,n,&got);if(result){error_code=400+result;return 0;}
 result=control(ep0,0xa1,0x81,1,probe,n,&got);if(result||got<26){error_code=6;return 0;}
 payload_limit=get32(probe+22);if(probe[2]!=format||probe[3]!=frame||get32(probe+4)!=2000000u||payload_limit<512||payload_limit>1048576){error_code=7;return 0;}
 result=control(ep0,0x21,1,2,probe,n,&got);if(result){error_code=500+result;return 0;}
 toggle=flags=bad=0;used=length=0;fid=-1;running=1;return 1;
}
void uvc_bridge_poll(uint32_t now)
{
 uint16_t n=0;uint8_t result;
 if(!running)return;
 if(!(USBHSH->MIS_ST&USBHS_UMS_DEV_ATTACH)){error_code=8;uvc_bridge_stop();return;}
 if(ready){if((uint32_t)(now-ready_ms)<5000)return;ready=0;length=0;fid=-1;drops++;}
 result=USBHSH_GetEndpData(5,&toggle,packet,&n);if(result){errors++;return;}packets++;
 if(n>sizeof(packet)){error_code=9;uvc_bridge_stop();return;}
 unsigned skip=0;
 if(used==0&&n){skip=packet[0];if(n<2||skip<2||skip>n){bad=1;flags=0;}
  else{flags=packet[1];if((flags&1)!=fid){fid=flags&1;length=0;bad=0;}if(flags&0x40)bad=1;}}
 if(!bad&&n>=skip){unsigned bytes=n-skip;if(length+bytes<=sizeof(image)){memcpy(image+length,packet+skip,bytes);length+=bytes;}else bad=1;}
 used+=n;
 if(n<512||used>=payload_limit){used=0;if(flags&2){
  if(!bad&&length>=4&&image[0]==0xff&&image[1]==0xd8&&image[length-2]==0xff&&image[length-1]==0xd9){ready=1;ready_ms=now;frame_id++;}
  else{drops++;length=0;fid=-1;}
 }}
}
static int number(const char **p,uint32_t *v,char end)
{uint32_t x=0;unsigned count=0;while(**p>='0'&&**p<='9'){unsigned d=*(*p)++-'0';if(x>(0xffffffffu-d)/10||++count>10)return 0;x=x*10+d;}if(!count||**p!=end)return 0;if(end)(*p)++;*v=x;return 1;}
int uvc_bridge_command(const char *text,uint32_t now,void (*send)(const char *))
{
 char reply[192];const char *p;uint32_t id,offset;(void)now;
 if(!strcmp(text,"CAMERA_CAPS")){send("CAMERA_CAPS,1,160,120\n");return 1;}
 if(!strcmp(text,"CAMERA_START")){if(start())send("CAMERA_STARTED\n");else{snprintf(reply,sizeof(reply),"CAMERA_ERR,%lu\n",(unsigned long)error_code);uvc_bridge_stop();send(reply);}return 1;}
 if(!strcmp(text,"CAMERA_STOP")){uvc_bridge_stop();send("CAMERA_STOPPED\n");return 1;}
 if(!strcmp(text,"CAMERA_INFO")){snprintf(reply,sizeof(reply),"CAMERA_INFO,%u,%u,%lu,%lu,%lu,%lu,%lu,%lu\n",running,ready,(unsigned long)frame_id,(unsigned long)(ready?length:0),(unsigned long)packets,(unsigned long)errors,(unsigned long)drops,(unsigned long)error_code);send(reply);return 1;}
 if(!strncmp(text,"CAMERA_CHUNK,",13)){
  p=text+13;if(!number(&p,&id,',')||!number(&p,&offset,0)||!ready||id!=frame_id||offset>=length){send("CAMERA_ERR,CHUNK\n");return 1;}
  ready_ms=now; /* A valid reader keeps this exact frame; no mid-read replacement. */
  unsigned n=length-offset;if(n>64)n=64;int at=snprintf(reply,sizeof(reply),"CAMDATA,%lu,%lu,",(unsigned long)id,(unsigned long)offset);static const char hex[]="0123456789ABCDEF";
  for(unsigned i=0;i<n;i++){reply[at++]=hex[image[offset+i]>>4];reply[at++]=hex[image[offset+i]&15];}reply[at++]='\n';reply[at]=0;send(reply);return 1;
 }
 if(!strncmp(text,"CAMERA_RELEASE,",15)){
  p=text+15;if(!number(&p,&id,0)||!ready||id!=frame_id){send("CAMERA_ERR,RELEASE\n");return 1;}ready=0;length=0;fid=-1;send("CAMRELEASED\n");return 1;
 }
 return 0;
}
