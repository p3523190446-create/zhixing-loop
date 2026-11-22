#include "settings.h"
#include "settings_codec.h"
#include "storage_probe.h"
/* Last two 4KB sectors reserved exclusively for settings. Never chip-erase.
 * Alternate copies, CRC + separate final commit byte; keep previous copy.
 * One bounded SPI transaction per poll, no busy waits. */
volatile uint32_t settings_ready,settings_busy,settings_saved_mm=200,settings_sequence,settings_saved_muted;
volatile uint32_t settings_ui_active,settings_ui_status,settings_ui_ms,settings_error,settings_saves,settings_loaded;
static uint8_t owned[2],blank[2],active=2,target,phase,scan_sector,scan_unknown,pending_muted;
static uint16_t scan_offset,pending_mm;
static uint32_t deadline_start,last_poll,pending_seq;
static uint8_t record[32];
static uint32_t address(unsigned sector){return SETTINGS_BASE+sector*4096u;}
static int erased(const uint8_t *p,unsigned n){while(n--)if(*p++!=255)return 0;return 1;}
static void ui(uint32_t code,uint32_t now){settings_ui_status=code;settings_ui_active=1;settings_ui_ms=now;}
static void fail(uint32_t code,uint32_t now){settings_error=code;settings_busy=0;phase=0;storage_write_disable();ui(3,now);}
void settings_init(uint32_t now)
{
 unsigned s;uint8_t buf[32],muted;uint16_t mm;uint32_t seq;
 settings_ready=settings_busy=settings_loaded=settings_sequence=settings_error=settings_saves=0;settings_saved_mm=200;settings_saved_muted=0;
 settings_ui_active=settings_ui_status=0;active=2;phase=0;scan_sector=0;scan_offset=0;scan_unknown=0;last_poll=now-2;
 for(s=0;s<2;s++){
  owned[s]=blank[s]=0;
  if(!storage_ready || !storage_read(address(s),buf,32))continue;
  owned[s]=setting_magic(buf);blank[s]=erased(buf,32);
  if(setting_decode(buf,&seq,&mm,&muted) && (active==2 || (int32_t)(seq-settings_sequence)>0)){
   active=(uint8_t)s;settings_saved_mm=mm;settings_sequence=seq;settings_saved_muted=muted;settings_loaded=1;
  }
 }
 if(settings_loaded)ui(4,now);
}
void settings_request(uint16_t mm,uint8_t muted,uint32_t now)
{
 if(settings_busy)return;
 if(!settings_ready || mm<120 || mm>500 || mm%10 || muted>1){fail(1,now);return;}
 storage_probe_sample();
 if(!storage_ready || storage_status()&1u){fail(2,now);return;}
 if(settings_loaded && mm==settings_saved_mm && muted==settings_saved_muted){ui(2,now);return;}
 target=active==0?1:0;
 if(!owned[target] && !blank[target]){fail(3,now);return;}
 pending_mm=mm;pending_muted=muted;pending_seq=settings_sequence+1u;
 setting_encode(record,pending_seq,mm,muted);settings_busy=1;settings_error=0;
 phase=blank[target]?3:1;deadline_start=now;ui(1,now);
}
void settings_poll(uint32_t now)
{
 uint8_t buf[32];unsigned i;
 if(settings_ui_active && !settings_busy && (uint32_t)(now-settings_ui_ms)>=4000u)settings_ui_active=0;
 if((uint32_t)(now-last_poll)<2u)return;
 last_poll=now;
 if(!settings_ready && !settings_busy){
  if(!storage_ready)return;
  while(scan_sector<2 && owned[scan_sector]){++scan_sector;scan_offset=0;}
  if(scan_sector==2){settings_ready=!scan_unknown;if(scan_unknown)settings_error=3;return;}
  if(!blank[scan_sector]){scan_unknown=1;++scan_sector;scan_offset=0;return;}
  if(!storage_read(address(scan_sector)+scan_offset,buf,32)||!erased(buf,32)){
   blank[scan_sector]=0;scan_unknown=1;++scan_sector;scan_offset=0;return;
  }
  scan_offset+=32;if(scan_offset==4096){++scan_sector;scan_offset=0;}return;
 }
 if(!settings_busy)return;
 if((uint32_t)(now-deadline_start)>(phase==2 && scan_offset?5000u:1500u)){fail(4,now);return;}
 switch(phase){
 case 1:
  if(!storage_erase_sector(address(target))){fail(5,now);return;}
  blank[target]=0;phase=2;scan_offset=0;deadline_start=now;break;
 case 2:
  if(storage_status()&1u)return;
  if(!scan_offset)deadline_start=now;
  if(!storage_read(address(target)+scan_offset,buf,32)||!erased(buf,32)){fail(6,now);return;}
  scan_offset+=32;if(scan_offset==4096){blank[target]=1;phase=3;}break;
 case 3:
  if(!storage_program(address(target),record,31)){fail(7,now);return;}
  blank[target]=0;phase=4;deadline_start=now;break;
 case 4:
  if(storage_status()&1u)return;
  if(!storage_read(address(target),buf,32)){fail(8,now);return;}
  for(i=0;i<31;i++)if(buf[i]!=record[i]){fail(8,now);return;}
  if(buf[31]!=255){fail(8,now);return;}
  owned[target]=1;phase=5;break;
 case 5:
  if(!storage_program(address(target)+31,record+31,1)){fail(9,now);return;}
  phase=6;deadline_start=now;break;
 case 6:
  if(storage_status()&1u)return;
  if(!storage_read(address(target),buf,32)||memcmp(buf,record,32)){fail(10,now);return;}
  settings_saved_mm=pending_mm;settings_sequence=pending_seq;settings_saved_muted=pending_muted;settings_loaded=1;
  active=target;++settings_saves;settings_busy=0;phase=0;storage_write_disable();ui(2,now);break;
 default:fail(11,now);break;
 }
}
int settings_debug_read(uint32_t offset,uint8_t *out)
{return !settings_busy && offset<=8192u-32u && storage_read(SETTINGS_BASE+offset,out,32);}
