#ifndef MUTE_KEY_H
#define MUTE_KEY_H
#include <stdint.h>
typedef struct {uint8_t candidate,stable,streak,armed;uint32_t presses;} mute_key_t;
static inline void mute_key_init(mute_key_t *k,uint8_t high)
{k->candidate=k->stable=high!=0;k->streak=0;k->armed=high!=0;k->presses=0;}
/* One call per millisecond. A release arms the next press; a boot-held key
 * does not silently toggle sound. Holding never repeats. */
static inline uint8_t mute_key_sample(mute_key_t *k,uint8_t high)
{
    high=high!=0;
    if(high!=k->candidate){k->candidate=high;k->streak=1;}
    else if(k->streak<30)++k->streak;
    if(k->streak<30 || high==k->stable)return 0;
    k->stable=high;
    if(high){k->armed=1;return 0;}
    if(k->armed){k->armed=0;++k->presses;return 1;}
    return 0;
}
#endif
