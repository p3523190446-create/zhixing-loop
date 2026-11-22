#include <assert.h>
#include <stdio.h>
#include "warning_adjust.h"
int main(void)
{
    guard_t g;
    guard_config_t config={80,110,200,220,300,3};
    assert(guard_init(&g,&config,0));
    assert(warning_adjust(&g,-10)==300);
    assert(g.state==GUARD_FAULT && g.recovery_count==0 && g.last_good_ms==0);
    guard_update(&g,10,1,1,250);
    assert(g.state==GUARD_FAULT && g.recovery_count==1);
    warning_adjust(&g,10);
    assert(g.config.caution_on_mm==200 && g.config.caution_off_mm==220);
    assert(g.state==GUARD_FAULT && g.recovery_count==1 && g.last_good_ms==10);
    guard_update(&g,20,1,1,250);guard_update(&g,30,1,1,250);
    assert(g.state==GUARD_NORMAL);
    warning_adjust(&g,-10);
    guard_update(&g,40,1,1,250);
    assert(g.state==GUARD_CAUTION);
    warning_adjust(&g,10);
    guard_update(&g,50,1,1,250);
    assert(g.state==GUARD_NORMAL);
    assert(warning_adjust(&g,4294967295LL)==120);
    assert(warning_adjust(&g,-4294967295LL)==500);
    assert(g.config.sample_timeout_ms==300 && g.config.recovery_samples==3);
    guard_update(&g,350,0,0,0);
    assert(g.state==GUARD_FAULT && g.fault==GUARD_FAULT_STALE);
    warning_adjust(&g,1);
    assert(g.state==GUARD_FAULT && g.fault==GUARD_FAULT_STALE);
    puts("PASS: CW/CCW, limits, new-sample classification, stale fault and recovery preservation");
    return 0;
}
