/* Static acquisition only: UART4 PC10 TX -> sensor RX, PC11 RX <- sensor TX.
 * No actuator calls. No calibration or Flash writes are sent to the module. */
#include "debug.h"
#include "line_tracking.h"
#include "line_protocol.h"
#include <stdio.h>
#include <string.h>

static line_protocol_t data;
static volatile uint8_t rx[512];
static volatile unsigned head,tail;
static volatile uint32_t rx_bytes,uart_errors,overflows;
static uint32_t started_ms,seen_errors,seen_overflows;
static const char *tx;
static unsigned tx_index;
static uint8_t start_sent;

void UART4_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
void UART4_IRQHandler(void)
{
    uint32_t status=UART4->STATR;
    if(status & (USART_STATR_RXNE|USART_STATR_ORE|USART_STATR_NE|USART_STATR_FE|USART_STATR_PE)) {
        uint8_t byte=(uint8_t)UART4->DATAR;
        if(status & (USART_STATR_ORE|USART_STATR_NE|USART_STATR_FE|USART_STATR_PE))++uart_errors;
        else if(status & USART_STATR_RXNE) {
            unsigned next=(head+1u)&511u;
            ++rx_bytes;
            if(next==tail)++overflows;
            else {rx[head]=byte;head=next;}
        }
    }
}

void line_tracking_init(uint32_t now)
{
    GPIO_InitTypeDef gpio={0};USART_InitTypeDef uart={0};NVIC_InitTypeDef irq={0};
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOC|RCC_APB2Periph_AFIO,ENABLE);
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_UART4,ENABLE);
    GPIO_SetBits(GPIOC,GPIO_Pin_10);
    gpio.GPIO_Pin=GPIO_Pin_10;gpio.GPIO_Mode=GPIO_Mode_AF_PP;gpio.GPIO_Speed=GPIO_Speed_10MHz;
    GPIO_Init(GPIOC,&gpio);
    gpio.GPIO_Pin=GPIO_Pin_11;gpio.GPIO_Mode=GPIO_Mode_IN_FLOATING;GPIO_Init(GPIOC,&gpio);
    uart.USART_BaudRate=115200;uart.USART_WordLength=USART_WordLength_8b;
    uart.USART_StopBits=USART_StopBits_1;uart.USART_Parity=USART_Parity_No;
    uart.USART_HardwareFlowControl=USART_HardwareFlowControl_None;uart.USART_Mode=USART_Mode_Rx|USART_Mode_Tx;
    USART_Init(UART4,&uart);
    irq.NVIC_IRQChannel=UART4_IRQn;irq.NVIC_IRQChannelPreemptionPriority=3;
    irq.NVIC_IRQChannelSubPriority=0;irq.NVIC_IRQChannelCmd=ENABLE;NVIC_Init(&irq);
    (void)UART4->STATR;(void)UART4->DATAR;
    USART_ITConfig(UART4,USART_IT_RXNE,ENABLE);USART_Cmd(UART4,ENABLE);
    started_ms=now;
}

static int request_start(uint32_t now)
{
    if((uint32_t)(now-started_ms)<20000u || tx)return 0;
    tx="$0,1,1#";tx_index=0;start_sent=1;return 1;
}

void line_tracking_poll(uint32_t now)
{
    unsigned budget=128;
    if(seen_errors!=uart_errors || seen_overflows!=overflows) {
        /* A lost byte invalidates the buffered stream. Never publish a hybrid frame. */
        NVIC_DisableIRQ(UART4_IRQn);tail=head;
        seen_errors=uart_errors;seen_overflows=overflows;NVIC_EnableIRQ(UART4_IRQn);
        line_protocol_reset_frame(&data);
        /* Discard validity immediately; retain counts as transport diagnostics. */
        data.analog_ms=now-500u;data.digital_ms=now-500u;
    }
    while(budget-- && tail!=head) {
        uint8_t byte=rx[tail];tail=(tail+1u)&511u;
        line_protocol_byte(&data,byte,now);
    }
    /* Start once only. Automatic retries could abort a user's KEY calibration. */
    if(!start_sent)(void)request_start(now);
    if(tx && USART_GetFlagStatus(UART4,USART_FLAG_TXE)!=RESET) {
        USART_SendData(UART4,(uint8_t)tx[tx_index++]);
        if(!tx[tx_index])tx=0;
    }
}

int line_tracking_command(const char *command,uint32_t now,void (*reply)(const char *))
{
    char text[192];unsigned i,mask=0;
    uint32_t aa=data.analog_frames?(uint32_t)(now-data.analog_ms):0xFFFFFFFFu;
    uint32_t da=data.digital_frames?(uint32_t)(now-data.digital_ms):0xFFFFFFFFu;
    if(!strcmp(command,"LINE_ID"))reply("LINE_ID,YB_8LP_UART4_PC10_PC11_STATIC_V1\n");
    else if(!strcmp(command,"LINE_START"))reply(request_start(now)?"LINE_START,QUEUED\n":"LINE_START,WAIT_OR_BUSY\n");
    else if(!strcmp(command,"LINE_STATUS")) {
        snprintf(text,sizeof(text),"LINE_STATUS,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%u,%u,%u\n",
            (unsigned long)now,(unsigned long)rx_bytes,(unsigned long)data.analog_frames,
            (unsigned long)data.digital_frames,(unsigned long)data.rejected,(unsigned long)uart_errors,
            (unsigned long)overflows,(unsigned long)aa,(unsigned long)da,(unsigned)start_sent,
            (unsigned)line_protocol_fresh(data.analog_frames,data.analog_ms,now),
            (unsigned)line_protocol_fresh(data.digital_frames,data.digital_ms,now));reply(text);
    } else if(!strcmp(command,"LINE_ANALOG")) {
        snprintf(text,sizeof(text),"LINE_ANALOG,%lu,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",(unsigned long)aa,
            (unsigned)line_protocol_fresh(data.analog_frames,data.analog_ms,now),
            data.analog[0],data.analog[1],data.analog[2],data.analog[3],
            data.analog[4],data.analog[5],data.analog[6],data.analog[7]);reply(text);
    } else if(!strcmp(command,"LINE_DIGITAL")) {
        for(i=0;i<8;i++)mask|=(unsigned)data.digital[i]<<i;
        snprintf(text,sizeof(text),"LINE_DIGITAL,%lu,%u,%u\n",(unsigned long)da,
            (unsigned)line_protocol_fresh(data.digital_frames,data.digital_ms,now),mask);reply(text);
    } else return 0;
    return 1;
}
