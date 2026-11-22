#ifndef ENCODER_DECODE_H
#define ENCODER_DECODE_H
#include <stdint.h>
#include <limits.h>

/* Four valid Gray-code transitions make one electrical cycle. The number
 * of electrical cycles per physical click remains to be measured. */
typedef struct {
    uint8_t phase;
    int8_t partial;
    int32_t cycles;
    uint32_t transitions, invalid;
} encoder_decode_t;

static inline void encoder_decode_init(volatile encoder_decode_t *s, uint8_t phase)
{
    s->phase=phase&3u; s->partial=0; s->cycles=0;
    s->transitions=0; s->invalid=0;
}
static inline void encoder_decode_sample(volatile encoder_decode_t *s, uint8_t phase)
{
    static const int8_t movement[16]={0,-1,1,0, 1,0,0,-1, -1,0,0,1, 0,1,-1,0};
    uint8_t old=s->phase;
    int8_t delta;
    phase&=3u;
    if(phase==old)return;
    s->phase=phase; ++s->transitions;
    if((old^phase)==3u){s->partial=0; ++s->invalid; return;}
    delta=movement[old*4u+phase];
    s->partial+=delta;
    if(s->partial>=4){
        if(s->cycles<INT32_MAX)++s->cycles;
        s->partial=0;
    }else if(s->partial<=-4){
        if(s->cycles>INT32_MIN)--s->cycles;
        s->partial=0;
    }
}
#endif
