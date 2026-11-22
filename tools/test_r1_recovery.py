"""Exercise actual read_sensor/record_sample bodies with faulted ST API stubs.

This is a host regression, not evidence of a physical wire reconnect.
"""
from pathlib import Path
import hashlib,json,subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/r1_oled_dual'
source=ROOT/'board/r1_oled_dual/main.c'
s=source.read_text(encoding='utf-8')
a=s.index('static app_sample_t record_sample(')
b=s.index('static void write_output(',a)
body=s[a:b]
prefix=r'''
#include "app.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef int VL53L0X_Error;
typedef struct { unsigned char RangeStatus; unsigned short RangeMilliMeter; } VL53L0X_RangingMeasurementData_t;
#define VL53L0X_ERROR_TIME_OUT -7
static int device;
static unsigned tick_ms,range_rounds,range_valid_count,range_status,range_mm;
static int range_error,range_init_error,range_loaded_offset_um;
static unsigned range_correction_valid,range_corrected_mm,range_in_calibrated_interval;
typedef struct { unsigned round,mm,status;int error; } RangeRecord;
static RangeRecord range_history[32];static unsigned range_history_count;
static unsigned sensor_pending,last_sensor_start_ms,last_sensor_poll_ms;
static bool attempted;
static unsigned range_needs_reinit,range_reinit_attempts,range_reinit_successes,range_last_reinit_ms;
static int connected=1,initialized=1,shot_ready=1,quality=0,init_failure;
static unsigned initialize_calls,bus_calls;
static int range_bus_recover(void){++bus_calls;return connected?0:-20;}
static int initialize(void){++initialize_calls;if(init_failure)return -20;initialized=1;range_loaded_offset_um=13000;return 0;}
static int VL53L0X_StartMeasurement(int*d){(void)d;return connected&&initialized?0:-20;}
static int VL53L0X_GetMeasurementDataReady(int*d,unsigned char*r){(void)d;*r=shot_ready;return connected&&initialized?0:-20;}
static int VL53L0X_GetRangingMeasurementData(int*d,VL53L0X_RangingMeasurementData_t*m){(void)d;m->RangeStatus=quality;m->RangeMilliMeter=270;return connected&&initialized?0:-20;}
static int VL53L0X_StopMeasurement(int*d){(void)d;return 0;}
static int VL53L0X_ClearInterruptMask(int*d,int mask){(void)d;(void)mask;return connected?0:-20;}
'''
tests=r'''
static guard_t guard;
static void reset(unsigned now){
 tick_ms=now;range_rounds=range_valid_count=range_history_count=0;
 sensor_pending=attempted=range_init_error=range_error=0;
 range_needs_reinit=range_reinit_attempts=range_reinit_successes=0;
 range_last_reinit_ms=now;last_sensor_start_ms=last_sensor_poll_ms=now;
 range_loaded_offset_um=13000;range_correction_valid=0;
 connected=initialized=shot_ready=1;quality=init_failure=0;
 bus_calls=initialize_calls=0;
 {guard_config_t c={80,110,200,220,300,3};assert(guard_init(&guard,&c,now));}
}
static app_sample_t run_at(unsigned now){
 app_sample_t r;tick_ms=now;r=read_sensor(0);
 guard_update(&guard,tick_ms,r.available,r.valid,r.distance_mm);
 return r;
}
static void shot(unsigned now){assert(!run_at(now).available);assert(run_at(now+5).valid);}
int main(void){
 unsigned i,before;
 /* A sensor reboot after lost power refuses shots until reinitialized. */
 reset(0);shot(0);shot(100);shot(200);assert(guard.state==GUARD_NORMAL);
 connected=initialized=0;assert(!run_at(300).valid);assert(guard.state==GUARD_FAULT);
 assert(range_needs_reinit && range_loaded_offset_um==0);
 run_at(1000);assert(bus_calls==1 && initialize_calls==0);
 connected=1;run_at(1999);assert(bus_calls==1);
 run_at(2000);assert(range_reinit_successes==1 && initialize_calls==1);
 assert(guard.state==GUARD_FAULT);shot(2001);assert(guard.state==GUARD_FAULT);
 shot(2101);assert(guard.state==GUARD_FAULT);shot(2201);assert(guard.state==GUARD_NORMAL);
 assert(range_loaded_offset_um==13000);
 /* Repeated missing-wire failures are rate limited, remain FAULT. */
 reset(0);range_init_error=-20;range_needs_reinit=1;connected=0;
 for(i=0;i<=10000;i+=5)run_at(i);
 assert(bus_calls==10 && initialize_calls==0 && guard.state==GUARD_FAULT);
 connected=1;init_failure=1;run_at(11000);assert(initialize_calls==1 && range_needs_reinit);
 init_failure=0;run_at(12000);assert(range_reinit_successes==1);
 shot(12001);shot(12101);shot(12201);assert(guard.state==GUARD_NORMAL);
 /* A bad optical result stays a fault, without resetting a healthy bus. */
 reset(0);quality=4;run_at(0);assert(!run_at(5).valid && !range_needs_reinit);
 before=initialize_calls;quality=0;shot(100);shot(200);shot(300);
 assert(guard.state==GUARD_NORMAL && initialize_calls==before);
 /* Conversion stuck-not-ready routes through reinit; bounded retry. */
 reset(0);shot_ready=0;run_at(0);run_at(149);assert(sensor_pending);
 assert(!run_at(154).valid && range_needs_reinit && !sensor_pending);
 shot_ready=1;run_at(1000);shot(1001);shot(1101);shot(1201);
 assert(guard.state==GUARD_NORMAL);
 /* Unsigned retry elapsed time also works across tick wrap. */
 reset(0xfffffe00u);range_init_error=-20;range_needs_reinit=1;
 run_at(0x1e7u);assert(bus_calls==0);run_at(0x1e8u);assert(bus_calls==1);
 puts("PASS: transport reconnect, startup absent, retry bounds, initialization retry, three fresh samples, optical quality, conversion timeout, tick wrap");
 return 0;
}
'''
OUT.mkdir(parents=True,exist_ok=True)
c=OUT/'recovery_host_test.c';c.write_text(prefix+body+tests,encoding='utf-8')
tcc=ROOT.parent/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe'
exe=OUT/'recovery_host_test.exe'
cmd=[str(tcc),'-Wall','-I'+str(ROOT/'include'),str(c),str(ROOT/'src/guard.c'),'-o',str(exe)]
steps=[]
for args in [cmd,[str(exe)]]:
 r=subprocess.run(args,capture_output=True,text=True,timeout=15)
 steps.append({'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 if r.returncode:
  print(r.stdout+r.stderr);raise RuntimeError('recovery host regression failed')
 print(r.stdout+r.stderr)
record={'date':'2026-10-07','scope':'Actual sensor reader bodies with simulated ST APIs; not physical reconnect',
 'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'result':'HOST_REGRESSION_PASS','steps':steps}
(OUT/'recovery-host-verification.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
