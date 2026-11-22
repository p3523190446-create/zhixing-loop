#include "UART.h"
#include "vision_uart.h"
#include "servo_probe.h"

volatile UART_CTL Uart;
__attribute__((aligned(4))) uint8_t UART2_Tx_Buf[DEF_UARTx_TX_BUF_LEN];
__attribute__((aligned(4))) uint8_t UART2_Rx_Buf[DEF_UARTx_RX_BUF_LEN];
volatile uint32_t native_bus_resets,native_rx_bytes,native_tx_queued,native_rejected,native_overflows;
static uint32_t seen_reset;
static char command[96];static unsigned command_len;static uint8_t discarding;
static uint8_t replies[16][192];static uint16_t reply_len[16];static unsigned reply_offset;
static unsigned reply_head,reply_count;

/* Vendor ISR calls these legacy names; there is deliberately no UART hardware. */
void UART2_USB_Init(void){}
void UART2_ParaInit(uint8_t mode)
{
    (void)mode;
    memset((void*)&Uart,0,sizeof(Uart));
    Uart.Com_Cfg[0]=0x00;Uart.Com_Cfg[1]=0xC2;Uart.Com_Cfg[2]=0x01;
    Uart.Com_Cfg[6]=8;Uart.Com_Cfg[7]=DEF_UARTx_RX_TIMEOUT;
    Uart.Rx_TimeOutMax=DEF_UARTx_RX_TIMEOUT;++native_bus_resets;
}
static void reply(const char *text)
{
    unsigned n=(unsigned)strlen(text);
    if(n>192||reply_count==16){++native_overflows;return;}
    unsigned tail=(reply_head+reply_count)%16;
    memcpy(replies[tail],text,n);reply_len[tail]=(uint16_t)n;++reply_count;
}
static void dispatch(uint32_t now)
{
    if(!strcmp(command,"PING"))reply("PONG\n");
    else if(!strcmp(command,"NATIVE_ID"))reply("NATIVE_USBFS,1\n");
    else if(!strcmp(command,"NATIVE_FEATURES"))reply("NORMAL_USBFS,1\n");
    else if(!strcmp(command,"GIMBAL_CAPS"))reply("GIMBAL_CAPS,1\n");
    else if(!strcmp(command,"ZX_NATIVE_A01"))reply("ZX_NATIVE_A01\n");
    else if(!strcmp(command,"ZX_NATIVE_B02"))reply("ZX_NATIVE_B02\n");
    else if(!strcmp(command,"ZX_NATIVE_C03"))reply("ZX_NATIVE_C03\n");
    else if(!vision_usb_query(command,now,reply))++native_rejected;
}
void native_usb_poll(uint32_t now)
{
    uint8_t packet[64];unsigned n=0;
    NVIC_DisableIRQ(USBFS_IRQn);
    if(seen_reset!=native_bus_resets){
        servo_probe_stop();seen_reset=native_bus_resets;command_len=0;discarding=0;reply_head=0;reply_count=0;reply_offset=0;
    }
    if(Uart.Tx_RemainNum){
        unsigned slot=Uart.Tx_DealNum;n=Uart.Tx_PackLen[slot];
        if(n<=64)memcpy(packet,&UART2_Tx_Buf[slot*DEF_USB_FS_PACK_LEN],n);
        else {n=0;++native_overflows;}
        Uart.Tx_DealNum=(uint16_t)((slot+1)%DEF_UARTx_TX_BUF_NUM_MAX);--Uart.Tx_RemainNum;
        if(Uart.USB_Down_StopFlag&&Uart.Tx_RemainNum<DEF_UARTx_TX_BUF_NUM_MAX-2){
            Uart.USB_Down_StopFlag=0;
            USBFSD->UEP2_RX_CTRL=(USBFSD->UEP2_RX_CTRL&~USBFS_UEP_R_RES_MASK)|USBFS_UEP_R_RES_ACK;
        }
    }
    NVIC_EnableIRQ(USBFS_IRQn);
    if(!USBFS_DevEnumStatus || (USBFS_DevSleepStatus&2u)){
        servo_probe_stop();command_len=0;discarding=0;reply_head=0;reply_count=0;reply_offset=0;return;
    }
    for(unsigned i=0;i<n;i++){
        uint8_t ch=packet[i];++native_rx_bytes;
        if(ch=='\n'){
            if(discarding){++native_rejected;reply("ERR,LINE\n");}
            else {command[command_len]=0;dispatch(now);}
            command_len=0;discarding=0;
        }else if(ch=='\r'){
            /* Native serial diagnostic uses LF commands; CR is rejected. */
            discarding=1;
        }else if(ch<32||ch>126||command_len>=sizeof(command)-1)discarding=1;
        else if(!discarding)command[command_len++]=(char)ch;
    }
    NVIC_DisableIRQ(USBFS_IRQn);
    /* A USB reset during parsing invalidates the pending response, never replay it. */
    if(seen_reset==native_bus_resets&&USBFS_DevEnumStatus&&reply_count&&!USBFS_Endp_Busy[DEF_UEP3]){
        unsigned chunk=reply_len[reply_head]-reply_offset;
        if(chunk>64)chunk=64;
        if(USBFS_Endp_DataUp(DEF_UEP3,replies[reply_head]+reply_offset,chunk,DEF_UEP_CPY_LOAD)==0){
            ++native_tx_queued;reply_offset+=chunk;
            if(reply_offset==reply_len[reply_head]){reply_offset=0;reply_head=(reply_head+1)%16;--reply_count;}
        }
    }
    NVIC_EnableIRQ(USBFS_IRQn);
}
