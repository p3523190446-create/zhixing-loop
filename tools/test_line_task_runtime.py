"""Exercise the production task adapter against fake input and motor ports only."""
from pathlib import Path
import json,subprocess
ROOT=Path(__file__).resolve().parents[2];SOURCE=ROOT/'知行回路软件/board/r1_line_task';OUT=ROOT/'知行回路软件/build/r1_line_task/runtime-test'
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'line_tracking.h').write_text('#include "line_task.h"\nvoid line_tracking_task_input(uint32_t now,lt_input *p);\n',encoding='utf-8')
(OUT/'remote_drive.h').write_text('#include <stdint.h>\nextern volatile uint32_t remote_drive_armed;\nvoid remote_drive_stop(uint32_t why);\n',encoding='utf-8')
test=r'''
#include "line_task_runtime.h"
#include "line_task.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
volatile uint32_t remote_drive_armed,led_last_good_ms,range_correction_valid=1,range_corrected_mm=1000,warning_mm=200;
static lt_input sample;static unsigned starts,sets,stops;static char answer[200];
void line_tracking_task_input(uint32_t now,lt_input *p){(void)now;*p=sample;}
void remote_drive_stop(uint32_t why){(void)why;++stops;remote_drive_armed=0;}
static int last_uart_owner;
int remote_drive_task_begin(uint32_t now,int uart_owner){(void)now;last_uart_owner=uart_owner;++starts;remote_drive_armed=1;return 1;}
int remote_drive_task_set(uint32_t now,int l,int r){(void)now;assert(l>=-100&&l<=100&&r>=-100&&r<=100);++sets;return 1;}
static void reply(const char *s){strcpy(answer,s);}
static void command(const char *s,unsigned now){assert(line_task_command(s,now,reply));}
int main(void){unsigned i;memset(&sample,0,sizeof(sample));sample.valid=1;sample.analog_frames=sample.digital_frames=1;sample.white_mask=0xe7;for(i=0;i<8;i++)sample.raw[i]=(i==3||i==4)?3300:250;
 command("LINE_TASK_CAL_CAPS",100);assert(!strcmp(answer,"LINE_TASK_CAL_CAPS,1,8\n"));
 command("LINE_TASK_CAL_SET,220,246,251,248,249,258,258,226,3145,3452,3456,3414,3331,3352,3357,2969",100);assert(strstr(answer,"LINE_TASK_CAL_SAVED,"));assert(lt_calibration_ready());
 {uint16_t f[8],b[8];uint32_t id=lt_get_calibration(f,b);assert(f[0]==220&&b[7]==2969);
 command("LINE_TASK_CAL_SET,1,2,3",100);assert(strstr(answer,"ERR,"));assert(lt_get_calibration(f,b)==id);
 command("LINE_TASK_CAL_SET,65536,246,251,248,249,258,258,226,3145,3452,3456,3414,3331,3352,3357,2969",100);assert(strstr(answer,"ERR,"));assert(lt_get_calibration(f,b)==id);
 command("LINE_TASK_CAL_SET,220,246,251,248,249,258,258,226,3145,3452,3456,3414,3331,3352,3357,2969,0",100);assert(strstr(answer,"ERR,"));assert(lt_get_calibration(f,b)==id);
 remote_drive_armed=1;command("LINE_TASK_CAL_SET,220,246,251,248,249,258,258,226,3145,3452,3456,3414,3331,3352,3357,2969",100);assert(strstr(answer,"ERR,"));remote_drive_armed=0;
 sample.white_mask=0;lt_classify(&sample);assert(sample.white_mask==0xe7);
 for(i=0;i<8;i++){f[i]=1202+i;b[i]=3202+i;}assert(lt_set_calibration(f,b));assert(lt_get_calibration(f,b)==2601406469u);
 for(i=0;i<8;i++)sample.raw[i]=(i==3||i==4)?3202+i:1202+i;lt_classify(&sample);assert(sample.white_mask==0xe7);}
 command("LINE_TASK_CONFIG,1,0,60,10000",100);assert(!strcmp(answer,"LINE_TASK_CONFIGURED\n"));
 command("LINE_TASK_CONFIG,1,0,60,10000,5",100);assert(!strcmp(answer,"ERR,LINE_TASK_CONFIG\n"));
 command("LINE_TASK_CONFIG,1,0,4294967356,10000",100);assert(!strcmp(answer,"ERR,LINE_TASK_CONFIG\n"));
 command("LINE_TASK_CONFIG,1,0,-60,10000",100);assert(!strcmp(answer,"ERR,LINE_TASK_CONFIG\n"));
 led_last_good_ms=100;command("LINE_TASK_START",100);
#if LINE_TASK_GROUND_READY
 assert(!strcmp(answer,"LINE_TASK_STARTED\n")&&starts==1&&sets==0);++sample.analog_frames;++sample.digital_frames;line_task_poll(120);assert(sets==1&&line_task_running());
 command("LINE_TASK_STATUS",500);line_task_poll(601);assert(!line_task_running()&&remote_drive_armed==0&&stops>0); /* Reads do not renew the 500ms lease. */
 led_last_good_ms=700;assert(line_task_usb_command("LINE_TASK_START",700,reply));assert(line_task_running()&&last_uart_owner==0);range_correction_valid=0;++sample.analog_frames;++sample.digital_frames;line_task_poll(720);assert(!line_task_running()&&remote_drive_armed==0);
 puts("PASS runtime: fake ports only, zero start, bounded requests, lease expiry, status cannot renew, range invalid stop");
#else
 assert(!strcmp(answer,"ERR,LINE_TASK_GROUND_NOT_ACCEPTED_OR_BUSY\n")&&starts==0&&sets==0);
 command("LINE_TASK_CAPS",100);assert(strstr(answer,",0\n"));puts("PASS production gate: ground permission off, no arm or vector issued, strict config validation");
#endif
 return 0;}
'''
c=OUT/'runtime_test.c';c.write_text(test,encoding='utf-8');cc=ROOT/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe';steps=[]
for enabled in (0,1):
 exe=OUT/f'runtime-{enabled}.exe'
 for args in ([cc,'-Wall',f'-DLINE_TASK_GROUND_READY={enabled}','-I'+str(OUT),'-I'+str(SOURCE),c,SOURCE/'line_task.c',SOURCE/'line_task_runtime.c','-o',exe],[exe]):
  p=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=30);steps.append(dict(ground_gate=enabled,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));print(p.stdout+p.stderr,end='')
  if p.returncode:raise SystemExit(p.returncode)
(OUT.parent/'runtime-verification.json').write_text(json.dumps(dict(result='PASS',scope='production C adapter with fake input/driver ports, no physical devices',steps=steps),indent=2),encoding='utf-8')
