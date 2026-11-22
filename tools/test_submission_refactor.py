"""Compare old/new production C on identical controlled input, without hardware."""
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BEFORE = ROOT / 'output/code-review-20261028/before'
SOURCE = ROOT / '知行回路软件/board/r1_line_task'
OUT = ROOT / 'output/code-review-20261028/equivalence'
OUT.mkdir(parents=True, exist_ok=True)
CC = ROOT / 'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe'
exports = ['lt_init', 'lt_start', 'lt_step', 'lt_stop', 'lt_active', 'lt_set_calibration',
           'lt_calibration_ready', 'lt_get_calibration', 'lt_classify', 'line_task_poll',
           'line_task_command', 'line_task_usb_command', 'line_task_running']
rename = ['-D' + name + '=old_' + name for name in exports]
stubs = OUT / 'stubs'
stubs.mkdir(exist_ok=True)
(stubs / 'line_tracking.h').write_text('#include "line_task.h"\nvoid line_tracking_task_input(uint32_t,lt_input*);\n')
(stubs / 'remote_drive.h').write_text('#include <stdint.h>\nextern volatile uint32_t remote_drive_armed;\nvoid remote_drive_stop(uint32_t);\n')
harness = r'''
#include "line_task.h"
#include "line_task_runtime.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int old_lt_start(lt_task*,const lt_config*,const lt_input*,uint32_t);
void old_lt_step(lt_task*,const lt_input*,uint32_t);
void old_lt_stop(lt_task*);
int old_lt_set_calibration(const uint16_t*,const uint16_t*);
void old_lt_classify(lt_input*);
int old_line_task_command(const char*,uint32_t,void(*)(const char*));
volatile uint32_t remote_drive_armed,led_last_good_ms,range_correction_valid=1,range_corrected_mm=1000,warning_mm=200;
void remote_drive_stop(uint32_t why){(void)why;remote_drive_armed=0;}
int remote_drive_task_begin(uint32_t now,int owner){(void)now;(void)owner;assert(0);return 0;}
int remote_drive_task_set(uint32_t now,int l,int r){(void)now;(void)l;(void)r;assert(0);return 0;}
void line_tracking_task_input(uint32_t now,lt_input *p){(void)now;memset(p,0,sizeof(*p));}
static uint32_t seed=27028;
static uint32_t random_word(void){seed=seed*1664525u+1013904223u;return seed;}
static char old_reply[200],new_reply[200];
static void old_answer(const char *s){assert(strlen(s)<sizeof(old_reply));strcpy(old_reply,s);}
static void new_answer(const char *s){assert(strlen(s)<sizeof(new_reply));strcpy(new_reply,s);}
static void same_command(const char *s,uint32_t now){
 int a,b;old_reply[0]=new_reply[0]=0;
 a=old_line_task_command(s,now,old_answer);b=line_task_command(s,now,new_answer);
 assert(a==b&&!strcmp(old_reply,new_reply));
}
int main(void){
 lt_task a,b;lt_input p,q;lt_config c={1,0,60,10000};uint32_t now=0xfffffff0u;unsigned i,j;
 uint16_t floor[8]={220,246,251,248,249,258,258,226},dark[8]={3145,3452,3456,3414,3331,3352,3357,2969};
 assert(old_lt_set_calibration(floor,dark)==lt_set_calibration(floor,dark));
 memset(&p,0,sizeof(p));p.valid=p.permit=1;p.white_mask=0xe7;p.analog_frames=p.digital_frames=1;
 assert(old_lt_start(&a,&c,&p,now)==lt_start(&b,&c,&p,now));
 for(i=0;i<100000;i++){
  uint32_t r=random_word();now+=(r>>24)%180;
  p.valid=(r&31)!=0;p.permit=(r&63)!=0;p.white_mask=(r>>8)&255;
  p.analog_age=(r>>16)%170;p.digital_age=(r>>20)%170;
  if(r&1)++p.analog_frames;if(r&2)++p.digital_frames;
  for(j=0;j<8;j++)p.raw[j]=(uint16_t)(random_word()%65536);
  q=p;old_lt_classify(&p);lt_classify(&q);assert(!memcmp(&p,&q,sizeof(p)));
  if(i%16==0){
   c.x1_left=(r&1)?1:-1;c.branch=(r>>4)%5;c.speed=39+(r%63);c.max_ms=999+(r%9003);
   assert(old_lt_start(&a,&c,&p,now)==lt_start(&b,&c,&p,now));
  }else if(i%97==0){old_lt_stop(&a);lt_stop(&b);}
  else{old_lt_step(&a,&p,now);lt_step(&b,&p,now);}
  assert(!memcmp(&a,&b,sizeof(a)));
 }
 same_command("LINE_TASK_CAL_SET,220,246,251,248,249,258,258,226,3145,3452,3456,3414,3331,3352,3357,2969",now);
 for(i=0;i<50000;i++){
  char text[192];uint32_t r=random_word();
  switch(i%10){
   case 0:snprintf(text,sizeof(text),"LINE_TASK_CONFIG,%s,%lu,%lu,%lu",r&1?"1":"-1",(unsigned long)(r%6),(unsigned long)(r%110),(unsigned long)(r%11000));break;
   case 1:strcpy(text,"LINE_TASK_CAL_GET");break;
   case 2:snprintf(text,sizeof(text),"LINE_TASK_CAL_SET,%lu,0,0,0,0,0,0,0,65535,65535,65535,65535,65535,65535,65535,65535",(unsigned long)r);break;
   case 3:strcpy(text,"LINE_TASK_START");break;
   case 4:strcpy(text,"LINE_TASK_STOP");break;
   case 5:strcpy(text,"LINE_TASK_STATUS");break;
   case 6:strcpy(text,"LINE_TASK_KEEPALIVE");break;
   case 7:strcpy(text,"LINE_TASK_CONFIG,-1,0000003,0000100,00010000");break;
   case 8:strcpy(text,"LINE_TASK_CONFIG,1,0,60,10000,extra");break;
   default:strcpy(text,"NOT_A_TASK_COMMAND");break;
  }
  same_command(text,now+i);
 }
 puts("PASS: 100000 core transitions and 50001 command comparisons; controlled inputs only");return 0;
}
'''
test = OUT / 'compare.c'
test.write_text(harness, encoding='utf-8')
objects = []
for prefix, source, defines in [('old', BEFORE, rename), ('new', SOURCE, [])]:
    for name in ['line_task.c', 'line_task_runtime.c']:
        obj = OUT / (prefix + '-' + name + '.o')
        subprocess.run(list(map(str, [CC, '-Wall', *defines, '-I' + str(source), '-I' + str(stubs),
                                      '-c', source / name, '-o', obj])), check=True)
        objects.append(obj)
exe = OUT / 'compare.exe'
subprocess.run(list(map(str, [CC, '-Wall', '-I' + str(SOURCE), test, *objects, '-o', exe])), check=True)
p = subprocess.run([str(exe)], capture_output=True, text=True, check=True)
report = dict(result='PASS', core_transitions=100000, command_comparisons=50001,
              scope='deterministic controlled old/new C comparison, not hardware acceptance',
              output=p.stdout.strip())
(OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report))
