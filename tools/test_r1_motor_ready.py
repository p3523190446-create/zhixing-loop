"""Fault injection into actual 250ms pulse watchdog body; not hardware evidence."""
from pathlib import Path
import subprocess,json,sys
root=Path(__file__).resolve().parents[2];out=root/'知行回路软件/build'/(sys.argv[1] if len(sys.argv)>1 else 'r1_motor_ready')
s=(out/'source-snapshot/motor_probe.c').read_text(encoding='utf8')
body=s[s.index('void motor_bench_tick(uint32_t now)'):]
prefix='''#include <stdint.h>
#include <assert.h>
#include <stdio.h>
static uint32_t motion_deadline_ms=250,motor_pulse_active,motor_speed_mode,motor_pulse_started_ms,motor_speed_frames,motor_speed_last_ms,motor_encoder_frames,motor_encoder_last_ms,motor_voltage_frames,motor_voltage_last_ms,motor_voltage_mv,motor_rx_errors,motor_rx_drops;
static int stops;
void motor_remote_stop_now(void){motor_pulse_active=0;++stops;}
'''
tests='''
static void reset(void){motor_pulse_active=motor_speed_frames=motor_encoder_frames=motor_voltage_frames=1;motor_speed_mode=motor_rx_errors=motor_rx_drops=stops=0;motor_pulse_started_ms=motor_speed_last_ms=motor_encoder_last_ms=motor_voltage_last_ms=1000;motor_voltage_mv=7900;}
int main(void){
reset();motor_bench_tick(1249);assert(motor_pulse_active);motor_bench_tick(1250);assert(!motor_pulse_active&&stops==1);
reset();motor_speed_frames=0;motor_bench_tick(1001);assert(stops==1);
reset();motor_encoder_frames=0;motor_bench_tick(1001);assert(stops==1);
reset();motor_voltage_mv=5999;motor_bench_tick(1001);assert(stops==1);
reset();motor_voltage_mv=8501;motor_bench_tick(1001);assert(stops==1);
reset();motor_rx_errors=1;motor_bench_tick(1001);assert(stops==1);
reset();motor_rx_drops=1;motor_bench_tick(1001);assert(stops==1);
reset();motor_pulse_started_ms=0xffffff80u;motor_speed_last_ms=motor_encoder_last_ms=motor_voltage_last_ms=100;motor_bench_tick(121);assert(stops==0);motor_bench_tick(122);assert(stops==1);
'''
if '>=motion_deadline_ms' in body:
 tests+='''reset();motor_speed_mode=4;motion_deadline_ms=2200;motor_speed_last_ms=motor_encoder_last_ms=motor_voltage_last_ms=3199;motor_bench_tick(3199);assert(stops==0);motor_bench_tick(3200);assert(stops==1);
'''
tests+='''puts("PASS:pulse watchdog deadline/fault/wrap and supported hold profile; host injection only");return 0;}
'''
c=out/'pulse_watchdog_test.c';c.write_text(prefix+body+tests,encoding='utf8');exe=out/'pulse_watchdog_test.exe'
cc=root/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe';steps=[]
for args in [[str(cc),'-Wall',str(c),'-o',str(exe)],[str(exe)]]:
 p=subprocess.run(args,capture_output=True,text=True,timeout=20);steps.append(dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));print(p.stdout+p.stderr);assert p.returncode==0
(out/'pulse-watchdog-verification.json').write_text(json.dumps(dict(result='PASS',scope='actual C timer body with injected counters',steps=steps),indent=2)+'\n',encoding='utf8')
