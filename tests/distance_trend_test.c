#include <assert.h>
#include <stdio.h>
#include "distance_trend.h"
int main(void)
{
    distance_trend_t s;unsigned i;
    distance_trend_reset(&s);
    for(i=0;i<7;i++)distance_trend_sample(&s,100*i,1,(uint16_t)(300-10*i));
    assert(s.valid && s.kind==TREND_CLOSING && s.closing_mm_s==100);
    distance_trend_reset(&s);
    for(i=0;i<7;i++)distance_trend_sample(&s,100*i,1,(uint16_t)(200+10*i));
    assert(s.valid && s.kind==TREND_AWAY && s.closing_mm_s==-100);
    distance_trend_reset(&s);
    for(i=0;i<25;i++)distance_trend_sample(&s,100*i,1,(uint16_t)(240+(i%2?2:-2)));
    assert(s.valid && s.kind==TREND_STILL);
    distance_trend_expire(&s,2700);assert(!s.valid && !s.count);
    for(i=0;i<7;i++)distance_trend_sample(&s,3000+100*i,1,250);
    assert(s.valid);distance_trend_sample(&s,3700,0,0);
    assert(!s.valid && s.kind==TREND_UNKNOWN);
    distance_trend_reset(&s);
    for(i=0;i<7;i++)distance_trend_sample(&s,0xfffffff0u+100*i,1,(uint16_t)(300-10*i));
    assert(s.valid && s.closing_mm_s==100);
    distance_trend_reset(&s);
    for(i=0;i<7;i++)distance_trend_sample(&s,110*i,1,(uint16_t)(300-11*i));
    assert(s.valid && s.closing_mm_s==100);
    distance_trend_sample(&s,660,1,0);assert(s.closing_mm_s==100); /* duplicate timestamp */
    puts("PASS: approach, retreat, stationary noise, fault/gap, clock wrap, irregular timing");
    return 0;
}
