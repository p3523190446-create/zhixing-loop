#ifndef USER_KEY_H
#define USER_KEY_H
#include <stdint.h>
typedef struct {uint8_t candidate,stable,streak,armed,active,long_sent;uint16_t held;uint32_t presses,shorts,longs;} user_key_t;
static inline void user_key_init(user_key_t *k,uint8_t high)
{k->candidate=k->stable=high!=0;k->streak=0;k->armed=high!=0;k->active=k->long_sent=0;k->held=0;k->presses=k->shorts=k->longs=0;}
/* 1ms sampling. Short on release; long once at 2s, never both.
 * Boot-held is ignored until a debounced release. */
static inline uint8_t user_key_sample(user_key_t *k,uint8_t high)
{
 high=high!=0;
 if(high!=k->candidate){k->candidate=high;k->streak=1;}
 else if(k->streak<30)++k->streak;
 if(k->streak>=30 && high!=k->stable){
  k->stable=high;
  if(high){uint8_t short_event=k->active && !k->long_sent;k->armed=1;k->active=0;
   if(short_event){++k->shorts;return 1;}return 0;}
  if(k->armed){k->armed=0;k->active=1;k->long_sent=0;k->held=0;++k->presses;}
 }
 if(!high && !k->stable && k->active && !k->long_sent){
  if(k->held<2000)++k->held;
  if(k->held==2000){k->long_sent=1;++k->longs;return 2;}
 }
 return 0;
}
#endif
