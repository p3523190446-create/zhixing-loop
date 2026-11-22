#include <assert.h>
#include <stdio.h>
#include "encoder_decode.h"
int main(void)
{
    encoder_decode_t s;
    unsigned i;
    const uint8_t forward[]={1,0,2,3}, reverse[]={2,0,1,3};
    encoder_decode_init(&s,3);
    for(i=0;i<4;i++)encoder_decode_sample(&s,forward[i]);
    assert(s.cycles==1 && s.partial==0 && s.invalid==0);
    for(i=0;i<4;i++)encoder_decode_sample(&s,reverse[i]);
    assert(s.cycles==0 && s.partial==0);
    /* Contact bounce retraces an edge; no extra complete cycle. */
    encoder_decode_sample(&s,2);encoder_decode_sample(&s,3);
    encoder_decode_sample(&s,2);encoder_decode_sample(&s,3);
    assert(s.cycles==0 && s.partial==0);
    /* Both bits changed: missed phase must not invent direction. */
    encoder_decode_sample(&s,0);
    assert(s.invalid==1 && s.cycles==0 && s.partial==0);
    encoder_decode_init(&s,3);s.cycles=INT32_MAX;
    for(i=0;i<4;i++)encoder_decode_sample(&s,forward[i]);
    assert(s.cycles==INT32_MAX);
    encoder_decode_init(&s,3);s.cycles=INT32_MIN;
    for(i=0;i<4;i++)encoder_decode_sample(&s,reverse[i]);
    assert(s.cycles==INT32_MIN);
    puts("PASS: direction, reversal, bounce, missed phase, saturation");
    return 0;
}
