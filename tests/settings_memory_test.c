#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "user_key.h"
#include "settings.h"
#include "settings_codec.h"
#include "storage_probe.h"
static uint8_t memory[8192];
static unsigned writes,erases,stuck,check_cuts;
static uint16_t cut_old,cut_new;
volatile uint32_t storage_jedec_id=0xEF4017,storage_sr1,storage_sr2,storage_probes,storage_matches,storage_ready=1;
static void check_boot_copy(void)
{
 unsigned s;uint16_t mm=0,m;uint32_t seq=0,q;int got=0;
 if(!check_cuts)return;
 for(s=0;s<2;s++)if(setting_decode(memory+s*4096,&q,&m)&&(!got||(int32_t)(q-seq)>0)){got=1;seq=q;mm=m;}
 assert(got && (mm==cut_old||mm==cut_new));
}
void storage_probe_sample(void){storage_ready=1;}
void storage_write_disable(void){}
uint8_t storage_status(void){return stuck?1:0;}
int storage_read(uint32_t a,uint8_t *out,unsigned n)
{assert(a>=SETTINGS_BASE && a+n<=SETTINGS_BASE+8192 && n<=32);memcpy(out,memory+a-SETTINGS_BASE,n);return 1;}
int storage_program(uint32_t a,const uint8_t *data,unsigned n)
{unsigned i;assert(a>=SETTINGS_BASE&&a+n<=SETTINGS_BASE+8192&&(a&255)+n<=256);++writes;
 for(i=0;i<n;i++){memory[a-SETTINGS_BASE+i]&=data[i];check_boot_copy();}return 1;}
int storage_erase_sector(uint32_t a)
{unsigned i;assert(a==SETTINGS_BASE||a==SETTINGS_BASE+4096);++erases;
 for(i=0;i<4096;i++){memory[a-SETTINGS_BASE+i]=255;check_boot_copy();}return 1;}
#include "settings.c"
static uint32_t tick;
static void settle(void)
{unsigned i;for(i=0;i<4000&&!settings_ready;i++){tick+=2;settings_poll(tick);}assert(settings_ready);}
static void save(unsigned mm)
{unsigned i;settings_request((uint16_t)mm,tick);for(i=0;i<3000&&settings_busy;i++){tick+=2;settings_poll(tick);}assert(!settings_busy && settings_ui_status==2 && settings_saved_mm==mm);}
static unsigned keyrun(user_key_t *k,unsigned high,unsigned ticks)
{unsigned event=0;while(ticks--)event|=user_key_sample(k,(uint8_t)high);return event;}
int main(void)
{
 unsigned i,n;uint8_t backup[8192],buf[32];uint16_t mm;uint32_t seq;user_key_t key;
 user_key_init(&key,1);
 for(i=0;i<10;i++){assert(!keyrun(&key,0,3));assert(!keyrun(&key,1,3));}
 assert(!keyrun(&key,0,200));assert(keyrun(&key,1,30)==1);
 assert(keyrun(&key,0,4000)==2);assert(!keyrun(&key,0,4000));assert(!keyrun(&key,1,30));
 assert(key.shorts==1&&key.longs==1);
 user_key_init(&key,0);assert(!keyrun(&key,0,4000));assert(!keyrun(&key,1,30));
 assert(!keyrun(&key,0,1990));assert(keyrun(&key,1,30)==1);assert(key.longs==0);
 memset(memory,255,sizeof(memory));settings_init(0);settle();assert(!settings_loaded&&settings_saved_mm==200);
 save(250);assert(settings_sequence==1 && writes==2 && erases==0);
 n=writes;save(250);assert(writes==n);
 save(300);assert(settings_sequence==2 && erases==0);
 memcpy(backup,memory,sizeof(memory));
 cut_old=300;cut_new=350;check_cuts=1;save(350);check_cuts=0;
 assert(erases==1);settings_init(tick);settle();assert(settings_saved_mm==350);
 /* Interrupt after every state-machine poll, including erase verification.
  * Simulated boot must select the previous copy until commit, then the new. */
 for(n=0;n<140;n++){
  memcpy(memory,backup,sizeof(memory));settings_init(tick);settle();settings_request(350,tick);
  for(i=0;i<n&&settings_busy;i++){tick+=2;settings_poll(tick);}
  settings_init(tick);assert(settings_saved_mm==300||settings_saved_mm==350);
 }
 memcpy(memory,backup,sizeof(memory));memory[4096+16]^=1;
 settings_init(tick);settle();assert(settings_saved_mm==250);
 memset(memory,255,sizeof(memory));memory[100]=0;settings_init(tick);
 for(i=0;i<400;i++){tick+=2;settings_poll(tick);}assert(!settings_ready&&settings_error==3);
 n=writes;settings_request(250,tick);assert(settings_ui_status==3&&writes==n);
 memcpy(memory,backup,sizeof(memory));settings_init(tick);settle();settings_request(350,tick);
 stuck=1;tick+=1600;settings_poll(tick);stuck=0;assert(!settings_busy&&settings_error==4);
 settings_init(tick);assert(settings_saved_mm==300);
 setting_encode(buf,0xFFFFFFFFu,500);assert(setting_decode(buf,&seq,&mm)&&seq==0xFFFFFFFFu&&mm==500);
 buf[31]=255;assert(!setting_decode(buf,&seq,&mm));
 puts("PASS: short/long/bounce/boot-held, CRC fallback, dedup, bounded timeout, unknown data refused, every erase/program byte and 140 restart cut points preserve old-or-new settings");
 return 0;
}
