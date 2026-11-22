#include "debug.h"
#include "vision_uart.h"
#include "oled_probe.h"
#include "oled_display.h"
#include "oled_probe2.h"
#include "oled_display2.h"
#include "oled_probe3.h"
#include "oled_display3.h"
#include "vision_labels.h"
#include <stdio.h>
#include "encoder_decode.h"
extern volatile encoder_decode_t encoder_state;
extern volatile uint32_t warning_mm,warning_change_ms,warning_ui_active;
#include <string.h>

/* Receive only: this module never controls LEDs, buzzer, servo or motors.
 * R1 J2: RX1(PA10) <-> TX_0; TX1(PA9) <-> RX_0. 115200 8N1. */
volatile uint32_t phone_monitor_valid,phone_monitor_state,phone_monitor_last_ms;
volatile uint32_t vision_link_valid;
volatile uint32_t vision_valid, vision_seq, vision_class=255;
volatile uint32_t vision_score, vision_cx, vision_cy, vision_last_ms;
volatile uint32_t vision_accepted, vision_rejected, vision_rx_errors;
extern volatile uint32_t range_rounds, range_status, range_corrected_mm;
extern volatile int32_t range_init_error,range_error,range_loaded_offset_um;
extern volatile uint32_t range_needs_reinit,range_reinit_attempts,range_reinit_successes;
extern volatile uint32_t guard_state,red_is_on,green_is_on;

static volatile uint8_t rx[256];
static volatile uint32_t rx_head, rx_tail;
static uint8_t tx[256];
static uint32_t tx_head, tx_tail, seen_errors;
static char line[96];
static unsigned line_length;
static uint8_t discarding, have_sequence;

void USART1_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
void USART1_IRQHandler(void)
{
    uint32_t status=USART1->STATR;
    if(status & (USART_FLAG_RXNE|USART_FLAG_ORE|USART_FLAG_FE|USART_FLAG_NE|USART_FLAG_PE)){
        uint8_t byte=(uint8_t)USART1->DATAR; /* STATR then DATAR clears errors. */
        uint32_t next=(rx_head+1u)&255u;
        if(status & (USART_FLAG_ORE|USART_FLAG_FE|USART_FLAG_NE|USART_FLAG_PE)){
            ++vision_rx_errors;
        }else if(next==rx_tail){
            ++vision_rx_errors;
        }else{
            rx[rx_head]=byte;
            rx_head=next;
        }
    }
}

void vision_uart_init(void)
{
    GPIO_InitTypeDef gpio={0};
    USART_InitTypeDef uart={0};
    NVIC_InitTypeDef irq={0};
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA|RCC_APB2Periph_USART1,ENABLE);
    GPIO_SetBits(GPIOA,GPIO_Pin_9);
    gpio.GPIO_Pin=GPIO_Pin_9;gpio.GPIO_Mode=GPIO_Mode_AF_PP;gpio.GPIO_Speed=GPIO_Speed_10MHz;
    GPIO_Init(GPIOA,&gpio);
    gpio.GPIO_Pin=GPIO_Pin_10;gpio.GPIO_Mode=GPIO_Mode_IPU;
    GPIO_Init(GPIOA,&gpio);
    USART_StructInit(&uart);
    uart.USART_BaudRate=115200;
    uart.USART_Mode=USART_Mode_Rx|USART_Mode_Tx;
    USART_Init(USART1,&uart);
    irq.NVIC_IRQChannel=USART1_IRQn;
    irq.NVIC_IRQChannelPreemptionPriority=1; /* Warning timer stays priority 0. */
    irq.NVIC_IRQChannelSubPriority=0;irq.NVIC_IRQChannelCmd=ENABLE;
    NVIC_Init(&irq);
    USART_ITConfig(USART1,USART_IT_RXNE,ENABLE);
    USART_Cmd(USART1,ENABLE);
}

static void reply(const char *message)
{
    unsigned i, n=(unsigned)strlen(message);
    if(n>255u-((tx_head-tx_tail)&255u))return;
    for(i=0;i<n;i++){tx[tx_head]=(uint8_t)message[i];tx_head=(tx_head+1u)&255u;}
}
static uint8_t checksum(const char *s, unsigned n)
{
    unsigned i,b;uint8_t c=0;
    for(i=0;i<n;i++){
        c^=(uint8_t)s[i];
        for(b=0;b<8;b++)c=(uint8_t)((c<<1)^((c&128u)?7u:0u));
    }
    return c;
}
static int hex_digit(char c)
{
    if(c>='0' && c<='9')return c-'0';
    if(c>='A' && c<='F')return c-'A'+10;
    return -1;
}
static int decimal(const char **cursor,uint32_t *out,char terminator)
{
    const char *p=*cursor;uint32_t value=0;unsigned count=0;
    while(*p>='0' && *p<='9'){
        unsigned digit=(unsigned)(*p++-'0');
        if(value>(0xFFFFFFFFu-digit)/10u || ++count>10)return 0;
        value=value*10u+digit;
    }
    if(!count || *p!=terminator)return 0;
    *cursor=p+(terminator!=0);*out=value;return 1;
}
static void accept_line(uint32_t now)
{
    char *star;const char *p;char response[160];int hi,lo;
    uint32_t seq,cls,score,cx,cy;
    if(!strcmp(line,"HELLO")){
        have_sequence=0;phone_monitor_valid=0;vision_link_valid=0;vision_valid=0;vision_class=255;
        reply("ZXR,V1\n");return;
    }
    if(!strcmp(line,"PING")){reply("PONG\n");return;}
    if(!strcmp(line,"PARAM_STATUS")){
        snprintf(response,sizeof(response),"PARAM,%lu,%lu,%lu,%lu\n",
            (unsigned long)warning_mm,(unsigned long)(warning_mm+20u),
            (unsigned long)warning_ui_active,(unsigned long)(now-warning_change_ms));
        reply(response);return;
    }
    if(!strcmp(line,"ENCODER_STATUS")){
        snprintf(response,sizeof(response),"ENCODER,%u,%u,%ld,%d,%lu,%lu\n",
            (unsigned)(encoder_state.phase&1u),(unsigned)((encoder_state.phase>>1)&1u),
            (long)encoder_state.cycles,(int)encoder_state.partial,
            (unsigned long)encoder_state.transitions,(unsigned long)encoder_state.invalid);
        reply(response);return;
    }
    if(!strcmp(line,"VISION_LABEL")){
        unsigned i,n;
        n=(unsigned)snprintf(response,sizeof(response),"LABEL,%lu,",(unsigned long)vision_class);
        if(vision_link_valid && vision_valid && vision_class<80){
            const uint16_t *label=vision_label_codes[vision_class];
            for(i=0;i<7 && label[i] && n+5<sizeof(response);i++)
                n+=(unsigned)snprintf(response+n,sizeof(response)-n,"%04X",(unsigned)label[i]);
        }
        response[n++]='\n';response[n]=0;reply(response);return;
    }
    if(!strcmp(line,"PHONE_STATUS")){
        snprintf(response,sizeof(response),"PHONE,%lu,%lu,%lu,%lu,%lu\n",
            (unsigned long)phone_monitor_valid,(unsigned long)phone_monitor_state,
            (unsigned long)(now-phone_monitor_last_ms),(unsigned long)vision_link_valid,
            (unsigned long)vision_valid);
        reply(response);return;
    }
    if(!strcmp(line,"RECOVERY_STATUS")){
        snprintf(response,sizeof(response),"RECOVERY,%lu,%lu,%lu,%ld,%ld,%lu,%lu,%lu,%lu\n",
            (unsigned long)range_needs_reinit,(unsigned long)range_reinit_attempts,
            (unsigned long)range_reinit_successes,(long)range_init_error,(long)range_error,
            (unsigned long)guard_state,(unsigned long)red_is_on,(unsigned long)green_is_on,
            (unsigned long)range_loaded_offset_um);
        reply(response);return;
    }
    if(!strcmp(line,"OLED2_STATUS")){
        snprintf(response,sizeof(response),"OLED2,%lu,%lu,%lu,%lu,%lu\n",
            (unsigned long)oled2_scan_count,(unsigned long)oled2_ack_3c,(unsigned long)oled2_ack_3d,
            (unsigned long)oled2_bus_error,(unsigned long)oled2_idle_lines);
        reply(response);return;
    }
    if(!strcmp(line,"OLED2_SCREEN")){
        snprintf(response,sizeof(response),"SCREEN2,%lu,%lu,%lu\n",
            (unsigned long)oled_display2_frames,(unsigned long)oled_display2_ready,
            (unsigned long)oled_display2_errors);
        reply(response);return;
    }
    if(!strcmp(line,"OLED3_STATUS")){
        snprintf(response,sizeof(response),"OLED3,%lu,%lu,%lu,%lu,%lu\n",
            (unsigned long)oled3_scan_count,(unsigned long)oled3_ack_3c,(unsigned long)oled3_ack_3d,
            (unsigned long)oled3_bus_error,(unsigned long)oled3_idle_lines);
        reply(response);return;
    }
    if(!strcmp(line,"OLED3_SCREEN")){
        snprintf(response,sizeof(response),"SCREEN3,%lu,%lu,%lu\n",
            (unsigned long)oled_display3_frames,(unsigned long)oled_display3_ready,
            (unsigned long)oled_display3_errors);
        reply(response);return;
    }
    if(!strcmp(line,"OLED_SCREEN")){
        snprintf(response,sizeof(response),"SCREEN,%lu,%lu,%lu\n",
            (unsigned long)oled_display_frames,(unsigned long)oled_display_ready,
            (unsigned long)oled_display_errors);
        reply(response);return;
    }
    if(!strcmp(line,"OLED_STATUS")){
        snprintf(response,sizeof(response),"OLED,%lu,%lu,%lu,%lu,%lu\n",
            (unsigned long)oled_scan_count,(unsigned long)oled_ack_3c,(unsigned long)oled_ack_3d,
            (unsigned long)oled_bus_error,(unsigned long)oled_idle_lines);
        reply(response);return;
    }
    if(!strcmp(line,"STATUS")){
        snprintf(response,sizeof(response),"STATUS,%lu,%lu,%ld,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu\n",
            (unsigned long)now,(unsigned long)range_rounds,(long)range_init_error,
            (unsigned long)range_status,(unsigned long)range_corrected_mm,
            (unsigned long)vision_valid,(unsigned long)vision_class,(unsigned long)vision_seq,
            (unsigned long)vision_accepted,(unsigned long)vision_rejected,(unsigned long)vision_rx_errors);
        reply(response);return;
    }
    if(strncmp(line,"V1,",3) && strncmp(line,"H1,",3))goto bad;
    star=strchr(line,'*');
    if(!star || strlen(star)!=3)goto bad;
    hi=hex_digit(star[1]);lo=hex_digit(star[2]);
    if(hi<0 || lo<0 || checksum(line,(unsigned)(star-line))!=(uint8_t)(hi*16+lo))goto bad;
    *star=0;p=line+3;
    if(line[0]=='H'){
        uint32_t state;
        if(!decimal(&p,&state,0) || state>4u)goto bad;
        phone_monitor_state=state;phone_monitor_last_ms=now;phone_monitor_valid=1;
        if(state!=3u){vision_link_valid=0;vision_valid=0;vision_class=255;}
        snprintf(response,sizeof(response),"HEART,%lu\n",(unsigned long)state);
        reply(response);return;
    }
    if(!decimal(&p,&seq,',') || !decimal(&p,&cls,',') || !decimal(&p,&score,',') ||
       !decimal(&p,&cx,',') || !decimal(&p,&cy,0))goto bad;
    if((cls>79u && cls!=255u) || score>1000u || cx>1000u || cy>1000u)goto bad;
    if(cls==255u && (score || cx || cy))goto bad;
    if(have_sequence && (int32_t)(seq-vision_seq)<=0)goto bad;
    vision_seq=seq;vision_class=cls;vision_score=score;vision_cx=cx;vision_cy=cy;
    vision_last_ms=now;vision_link_valid=1;vision_valid=cls!=255u;have_sequence=1;++vision_accepted;
    snprintf(response,sizeof(response),"ACK,%lu,%lu,%lu,%lu,%lu\n",
        (unsigned long)seq,(unsigned long)cls,(unsigned long)score,(unsigned long)cx,(unsigned long)cy);
    reply(response);return;
bad:
    ++vision_rejected;reply("ERR\n");
}

void vision_uart_poll(uint32_t now)
{
    unsigned budget=128;
    if(seen_errors!=vision_rx_errors){
        seen_errors=vision_rx_errors;line_length=0;discarding=1;
        rx_tail=rx_head;phone_monitor_valid=0;vision_link_valid=0;vision_valid=0;vision_class=255;
    }
    while(budget-- && rx_tail!=rx_head){
        uint8_t byte=rx[rx_tail];rx_tail=(rx_tail+1u)&255u;
        if(byte=='\n'){
            if(!discarding && line_length){line[line_length]=0;accept_line(now);}
            else if(discarding)++vision_rejected;
            line_length=0;discarding=0;
        }else if(byte!='\r' && !discarding){
            if(byte<32 || byte>126 || line_length>=sizeof(line)-1){discarding=1;line_length=0;}
            else line[line_length++]=(char)byte;
        }
    }
    /* No stale target may survive a disconnected or stalled sender. */
    if((uint32_t)(now-vision_last_ms)>=2000u){vision_link_valid=0;vision_valid=0;vision_class=255;}
    if((uint32_t)(now-phone_monitor_last_ms)>=3500u)phone_monitor_valid=0;
    budget=16;
    while(budget-- && tx_tail!=tx_head && USART_GetFlagStatus(USART1,USART_FLAG_TXE)==SET){
        USART_SendData(USART1,tx[tx_tail]);tx_tail=(tx_tail+1u)&255u;
    }
}
