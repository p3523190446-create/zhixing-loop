#include "debug.h"
#include "storage_probe.h"
/* Read-only SPI mode 0. CS=PA3, SCK=PA5, DO/MISO=PA6, DI/MOSI=PA7.
 * Bounded 8-bit transfers, interrupts stay enabled. Never write-enable,
 * program, erase or modify status registers. */
volatile uint32_t storage_jedec_id,storage_sr1,storage_sr2;
volatile uint32_t storage_probes,storage_matches,storage_ready;
static void pause_half(void){Delay_Us(5);}
static uint8_t transfer(uint8_t out)
{
    unsigned i;uint8_t in=0;
    for(i=0;i<8;i++){
        GPIO_ResetBits(GPIOA,GPIO_Pin_5);
        if(out&0x80u)GPIO_SetBits(GPIOA,GPIO_Pin_7);
        else GPIO_ResetBits(GPIOA,GPIO_Pin_7);
        pause_half();GPIO_SetBits(GPIOA,GPIO_Pin_5);pause_half();
        in=(uint8_t)((in<<1)|((GPIOA->INDR>>6)&1u));
        GPIO_ResetBits(GPIOA,GPIO_Pin_5);out=(uint8_t)(out<<1);
    }
    return in;
}
static void select_chip(void)
{GPIO_ResetBits(GPIOA,GPIO_Pin_5);GPIO_ResetBits(GPIOA,GPIO_Pin_3);pause_half();}
static void release_chip(void)
{GPIO_SetBits(GPIOA,GPIO_Pin_3);GPIO_ResetBits(GPIOA,GPIO_Pin_7);pause_half();}
static uint8_t read_status(uint8_t command)
{uint8_t value;select_chip();transfer(command);value=transfer(0xFF);release_chip();return value;}
void storage_probe_sample(void)
{
    uint32_t id;select_chip();transfer(0x9F);
    id=(uint32_t)transfer(0xFF)<<16;
    id|=(uint32_t)transfer(0xFF)<<8;id|=transfer(0xFF);release_chip();
    storage_jedec_id=id;
    storage_sr1=read_status(0x05);storage_sr2=read_status(0x35);
    ++storage_probes;
    storage_ready=(id==0xEF4017u);
    if(storage_ready)++storage_matches;
}
void storage_probe_init(void)
{
    GPIO_InitTypeDef gpio={0};
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA,ENABLE);
    GPIO_SetBits(GPIOA,GPIO_Pin_3);GPIO_ResetBits(GPIOA,GPIO_Pin_5|GPIO_Pin_7);
    gpio.GPIO_Pin=GPIO_Pin_3|GPIO_Pin_5|GPIO_Pin_7;
    gpio.GPIO_Mode=GPIO_Mode_Out_PP;gpio.GPIO_Speed=GPIO_Speed_2MHz;
    GPIO_Init(GPIOA,&gpio);
    gpio.GPIO_Pin=GPIO_Pin_6;gpio.GPIO_Mode=GPIO_Mode_IPU;GPIO_Init(GPIOA,&gpio);
    storage_probe_sample();
}
