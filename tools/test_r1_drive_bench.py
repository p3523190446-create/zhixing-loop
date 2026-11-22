"""Execute the compiled DRIVE state machine with fault-injected telemetry."""
from pathlib import Path
import subprocess,json,hashlib,sys
root=Path(__file__).resolve().parents[2]
out=root/'知行回路软件/build'/(sys.argv[1] if len(sys.argv)>1 else 'r1_drive_bench')
u=out/'source-snapshot'
test=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "remote_drive.c"
volatile uint32_t led_last_good_ms,range_correction_valid,range_corrected_mm,warning_mm;
volatile uint32_t motor_voltage_mv,motor_voltage_last_ms,motor_voltage_frames;
volatile uint32_t motor_speed_frames,motor_speed_last_ms,motor_rx_errors,motor_rx_drops,motor_speed_fault,motor_pulse_active;
static int stops,writes;static int32_t written_l,written_r;static char response[256];
void motor_remote_stop_now(void){++stops;}
int motor_remote_write(int32_t l,int32_t r){++writes;written_l=l;written_r=r;return 1;}
static void reply(const char *s){strcpy(response,s);}
static void fresh(uint32_t n){led_last_good_ms=motor_speed_last_ms=motor_voltage_last_ms=n;}
static void cmd(const char *s,uint32_t n){remote_drive_uart_command(s,n,reply);}
static void reset(uint32_t n){
 remote_drive_stop(5);generation=sequence=0;seen_errors=seen_drops=error_changed_ms=0;
 motor_rx_errors=motor_rx_drops=motor_speed_fault=motor_pulse_active=0;
 range_correction_valid=1;range_corrected_mm=500;warning_mm=120;
 motor_voltage_mv=7900;motor_voltage_frames=motor_speed_frames=1;fresh(n);
}
int main(void){
 reset(2000);cmd("DRIVE_ARM",2000);assert(remote_drive_armed&&remote_drive_uart_owner);
 cmd("DRIVE_SET,1,1,-120,120",2001);remote_drive_poll(2001);assert(written_l==-120&&written_r==120&&remote_drive_moving);
 cmd("DRIVE_SET,1,1,250,250",2002);assert(!strcmp(response,"ERR,DRIVE_REJECTED\n"));assert(desired_left==-120);
 cmd("DRIVE_SET,1,2,251,0",2003);assert(!strcmp(response,"ERR,DRIVE_REJECTED\n"));
 cmd("DRIVE_BRAKE,1,2",2004);assert(!remote_drive_moving&&remote_drive_armed&&desired_left==0);
 fresh(2604);remote_drive_tick(2604);assert(!remote_drive_armed&&reason==1);
 cmd("DRIVE_SET,1,3,120,120",2605);assert(!remote_drive_armed);
 reset(3000);range_corrected_mm=120;cmd("DRIVE_ARM",3000);assert(!remote_drive_armed);
 reset(3000);led_last_good_ms=2700;cmd("DRIVE_ARM",3000);assert(!remote_drive_armed);
 reset(3000);motor_speed_frames=0;cmd("DRIVE_ARM",3000);assert(!remote_drive_armed);
 reset(3000);motor_voltage_mv=5999;cmd("DRIVE_ARM",3000);assert(!remote_drive_armed);
 reset(3000);motor_voltage_mv=8501;cmd("DRIVE_ARM",3000);assert(!remote_drive_armed);
 reset(3000);cmd("DRIVE_ARM",3000);motor_rx_errors=1;remote_drive_tick(3001);assert(!remote_drive_armed&&reason==4);
 fresh(4500);cmd("DRIVE_ARM",4500);assert(!remote_drive_armed);
 fresh(4501);cmd("DRIVE_ARM",4501);assert(remote_drive_armed);motor_rx_drops=1;remote_drive_tick(4502);assert(!remote_drive_armed&&reason==4);
 reset(5000);cmd("DRIVE_ARM",5000);range_corrected_mm=119;remote_drive_tick(5001);assert(!remote_drive_armed&&reason==2);
 reset(5000);remote_drive_command("DRIVE_ARM",5000,reply);assert(remote_drive_armed&&!remote_drive_uart_owner);
 remote_drive_stop(3);assert(!remote_drive_armed&&!remote_drive_uart_owner&&reason==3);
 reset(6000);cmd("DRIVE_ARM",6000);cmd("DRIVE_SET,1,1,0,0,garbage",6001);assert(!strcmp(response,"ERR,DRIVE_REJECTED\n"));
 puts("PASS:17 DRIVE motion/stop/freshness/error/ownership boundary scenarios; injected host telemetry only");
 return 0;
}
'''
c=out/'drive_state_test.c';c.write_text(test,encoding='utf8')
compiler=root/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe';exe=out/'drive_state_test.exe'
steps=[]
for args in [[str(compiler),'-Wall','-I'+str(u),str(c),'-o',str(exe)],[str(exe)]]:
 p=subprocess.run(args,capture_output=True,text=True,timeout=20)
 steps.append(dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
 print(p.stdout+p.stderr)
 assert p.returncode==0,steps
(out/'drive-state-verification.json').write_text(json.dumps(dict(result='PASS',scope='Actual compiled C protocol with injected telemetry; no hardware claim',source_sha256=hashlib.sha256((u/'remote_drive.c').read_bytes()).hexdigest(),steps=steps),indent=2)+'\n',encoding='utf8')
