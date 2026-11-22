#include "debug.h"
#include "motor_probe.h"

/* Diagnostic only: no nonzero speed/PWM, configuration or flash writes.
 * USART3 full remap: PD8 TX -> module RX2, PD9 RX <- module TX2.
 * Each boot releases PID with zero PWM, then queries battery voltage.
 * Bounded RX/TX servicing preserves ToF, three OLEDs and timer service. */
volatile uint32_t motor_rx_bytes,motor_rx_errors,motor_rx_drops;
volatile uint32_t motor_queries,motor_tx_bytes,motor_log_count,motor_last_rx_ms;
volatile uint8_t motor_log[128];
static volatile uint8_t rx[256];
static volatile uint32_t rx_head,rx_tail;
static const char *tx;
static uint32_t last_query_ms;
static uint8_t zero_sent,query_started;

void USART3_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
void USART3_IRQHandler(void)
{
    uint32_t status=USART3->STATR;
    if(status&(USART_FLAG_RXNE|USART_FLAG_ORE|USART_FLAG_FE|USART_FLAG_NE|USART_FLAG_PE)){
        uint8_t byte=(uint8_t)USART3->DATAR;
        uint32_t next=(rx_head+1u)&255u;
        if(status&(USART_FLAG_ORE|USART_FLAG_FE|USART_FLAG_NE|USART_FLAG_PE))++motor_rx_errors;
        else{
            ++motor_rx_bytes;
            if(next==rx_tail)++motor_rx_drops;
            else{rx[rx_head]=byte;rx_head=next;}
        }
    }
}

void motor_probe_init(void)
{
    GPIO_InitTypeDef gpio={0};USART_InitTypeDef uart={0};NVIC_InitTypeDef irq={0};
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_AFIO|RCC_APB2Periph_GPIOD,ENABLE);
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_USART3,ENABLE);
    GPIO_PinRemapConfig(GPIO_FullRemap_USART3,ENABLE);
    GPIO_SetBits(GPIOD,GPIO_Pin_8);
    gpio.GPIO_Pin=GPIO_Pin_8;gpio.GPIO_Mode=GPIO_Mode_AF_PP;gpio.GPIO_Speed=GPIO_Speed_10MHz;
    GPIO_Init(GPIOD,&gpio);
    gpio.GPIO_Pin=GPIO_Pin_9;gpio.GPIO_Mode=GPIO_Mode_IPU;GPIO_Init(GPIOD,&gpio);
    USART_StructInit(&uart);uart.USART_BaudRate=115200;
    uart.USART_Mode=USART_Mode_Rx|USART_Mode_Tx;USART_Init(USART3,&uart);
    irq.NVIC_IRQChannel=USART3_IRQn;irq.NVIC_IRQChannelPreemptionPriority=2;
    irq.NVIC_IRQChannelSubPriority=0;irq.NVIC_IRQChannelCmd=ENABLE;NVIC_Init(&irq);
    USART_ITConfig(USART3,USART_IT_RXNE,ENABLE);USART_Cmd(USART3,ENABLE);
}

void motor_probe_poll(uint32_t now)
{
    unsigned budget=32;
    while(rx_tail!=rx_head && budget--){
        motor_log[motor_log_count&127u]=rx[rx_tail];
        rx_tail=(rx_tail+1u)&255u;++motor_log_count;motor_last_rx_ms=now;
    }
    if(!tx){
        if(!zero_sent){tx="$pwm:0,0,0,0#";zero_sent=1;last_query_ms=now;}
        else if((uint32_t)(now-last_query_ms)>=(query_started?1000u:500u)){
            tx="$read_vol#";last_query_ms=now;query_started=1;++motor_queries;
        }
    }
    if(tx && USART_GetFlagStatus(USART3,USART_FLAG_TXE)!=RESET){
        USART_SendData(USART3,(uint8_t)*tx++);++motor_tx_bytes;
        if(!*tx)tx=0;
    }
}
