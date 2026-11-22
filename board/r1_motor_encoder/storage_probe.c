#include "debug.h"
#include "storage_probe.h"
/* Read-only SPI mode 0. CS=PA3, SCK=PA5, DO/MISO=PA6, DI/MOSI=PA7.
 * Bounded transfers; interrupts stay enabled. Data writes only in the
 * last two settings sectors, requested by a physical long USER press. */
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

uint8_t storage_status(void){return read_status(0x05);}
static void send_address(uint32_t a){transfer((uint8_t)(a>>16));transfer((uint8_t)(a>>8));transfer((uint8_t)a);}
int storage_read(uint32_t a,uint8_t *out,unsigned n)
{unsigned i;if(!out || n>32 || a>=0x800000u || n>0x800000u-a)return 0;
 select_chip();transfer(0x03);send_address(a);for(i=0;i<n;i++)out[i]=transfer(0xFF);release_chip();return 1;}
static int enable_write(void)
{if(storage_status()&1u)return 0;select_chip();transfer(0x06);release_chip();return (storage_status()&3u)==2u;}
void storage_write_disable(void){select_chip();transfer(0x04);release_chip();}
int storage_program(uint32_t a,const uint8_t *data,unsigned n)
{unsigned i;if(!data || !n || n>32 || a<0x7FE000u || a>=0x800000u || n>0x800000u-a || (a&255u)+n>256u || !enable_write())return 0;
 select_chip();transfer(0x02);send_address(a);for(i=0;i<n;i++)transfer(data[i]);release_chip();return 1;}
int storage_erase_sector(uint32_t a)
{if((a!=0x7FE000u && a!=0x7FF000u)||!enable_write())return 0;
 select_chip();transfer(0x20);send_address(a);release_chip();return 1;}
