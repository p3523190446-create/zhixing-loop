#include <assert.h>
#include <stdio.h>
#include "mute_key.h"
static unsigned run(mute_key_t *k,unsigned level,unsigned ticks)
{unsigned events=0;while(ticks--)events+=mute_key_sample(k,(uint8_t)level);return events;}
int main(void)
{
    mute_key_t k;unsigned i;
    mute_key_init(&k,1);
    for(i=0;i<10;i++){assert(run(&k,0,3)==0);assert(run(&k,1,3)==0);}
    assert(k.presses==0);
    assert(run(&k,0,29)==0);assert(run(&k,0,1)==1);
    assert(run(&k,0,1000)==0 && k.presses==1);
    assert(run(&k,1,30)==0);assert(run(&k,0,30)==1 && k.presses==2);
    mute_key_init(&k,0);assert(run(&k,0,1000)==0 && k.presses==0);
    assert(run(&k,1,30)==0);assert(run(&k,0,30)==1);
    puts("PASS: bounce rejected, 30ms debounce, one event per press, boot-held release-to-arm");
    return 0;
}
