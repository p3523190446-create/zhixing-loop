"""Host tests of the production C task core, no devices or actuator writes."""
from pathlib import Path
import json,subprocess
ROOT=Path(__file__).resolve().parents[2];SOURCE=ROOT/'知行回路软件/board/r1_line_task';OUT=ROOT/'知行回路软件/build/r1_line_task'
OUT.mkdir(parents=True,exist_ok=True)
test=r'''
#include "line_task.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static lt_input input(unsigned mask){unsigned i;lt_input p;memset(&p,0,sizeof(p));p.valid=p.permit=1;p.analog_frames=p.digital_frames=1;p.white_mask=mask;for(i=0;i<8;i++)p.raw[i]=(mask&(1u<<i))?250:3300;return p;}
static void tick(lt_task *s,lt_input *p,unsigned mask,uint32_t now){unsigned i;p->white_mask=mask;for(i=0;i<8;i++)p->raw[i]=(mask&(1u<<i))?250:3300;++p->analog_frames;++p->digital_frames;lt_step(s,p,now);}
int main(void){lt_task s;lt_input p=input(0xe7);lt_config c={1,LT_STOP,60,10000};
 assert(lt_start(&s,&c,&p,100));assert(s.left==0&&s.right==0);tick(&s,&p,0xe7,120);assert(s.state==LT_FOLLOW&&s.left>0&&s.right>0&&s.left<=100&&s.right<=100);
 tick(&s,&p,0xfe,140);assert(s.left<s.right);lt_stop(&s);assert(!lt_active(&s)&&s.left==0&&s.right==0);
 c.x1_left=-1;p=input(0xe7);assert(lt_start(&s,&c,&p,100));tick(&s,&p,0xfe,120);assert(s.left>s.right);
 c.x1_left=0;assert(!lt_start(&s,&c,&p,100)&&s.reason==LT_BAD_CONFIG);c.x1_left=1;
 p=input(0xe7);p.analog_age=150;assert(!lt_start(&s,&c,&p,100)&&s.reason==LT_STALE);
 p=input(0xe7);assert(lt_start(&s,&c,&p,100));tick(&s,&p,0xe7,120);p.digital_age=150;lt_step(&s,&p,121);assert(s.reason==LT_STALE&&s.left==0&&s.right==0);
 p=input(0xe7);assert(lt_start(&s,&c,&p,100));tick(&s,&p,0xff,120);assert(s.state==LT_FAULT&&s.reason==LT_LOST);
 p=input(0xe7);assert(lt_start(&s,&c,&p,100));p.permit=0;lt_step(&s,&p,101);assert(s.reason==LT_GUARD&&s.left==0);
 p=input(0xe7);assert(lt_start(&s,&c,&p,100));tick(&s,&p,0,120);assert(s.state==LT_JUNCTION&&s.left==0);lt_step(&s,&p,150);assert(s.junction_samples==1);tick(&s,&p,0,160);tick(&s,&p,0,180);assert(s.state==LT_DONE&&s.reason==LT_AT_JUNCTION&&s.junctions==1);
 tick(&s,&p,0xe7,200);assert(s.state==LT_DONE&&s.left==0); /* Never resume from a stop automatically. */
 c.branch=LT_LEFT;p=input(0xe7);assert(lt_start(&s,&c,&p,100));tick(&s,&p,0,120);tick(&s,&p,0,140);tick(&s,&p,0,160);assert(s.state==LT_TURN&&s.left<0&&s.right>0);tick(&s,&p,0xff,200);tick(&s,&p,0xe7,340);tick(&s,&p,0xe7,360);assert(s.state==LT_FOLLOW);
 c.branch=LT_RIGHT;p=input(0xe7);assert(lt_start(&s,&c,&p,100));tick(&s,&p,0,120);tick(&s,&p,0,140);tick(&s,&p,0,160);assert(s.left>0&&s.right<0);lt_step(&s,&p,1360);assert(s.state==LT_FAULT&&s.reason==LT_TURN_TIMEOUT&&s.left==0);
 c.branch=LT_STRAIGHT;p=input(0xe7);assert(lt_start(&s,&c,&p,100));tick(&s,&p,0,120);tick(&s,&p,0,140);tick(&s,&p,0,160);assert(s.left==s.right&&s.left>0);tick(&s,&p,0,240);tick(&s,&p,0xe7,340);tick(&s,&p,0xe7,360);assert(s.state==LT_FOLLOW);
 c.branch=LT_STOP;p=input(0xe7);assert(lt_start(&s,&c,&p,0xfffffff0u));tick(&s,&p,0xe7,20);assert(s.state==LT_FOLLOW);lt_step(&s,&p,10000);assert(s.reason==LT_TIME_LIMIT&&s.left==0);
 p=input(0xe7);assert(lt_start(&s,&c,&p,100));tick(&s,&p,0xe7,120);++p.analog_frames;lt_step(&s,&p,140);assert(s.last_update==120); /* Half-new pair does not advance task. */
 p=input(0xe7);assert(lt_start(&s,&c,&p,100));tick(&s,&p,0xe7,300);assert(s.reason==LT_STALE&&s.left==0); /* Fresh data cannot hide a stalled control loop. */
 puts("PASS: C line task start-at-zero/orientation/limits/lost/stale/guard/junction-debounce/duplicate/no-resume/left/right/straight/reacquire/timeout/wrap/half-frame");return 0;}
'''
c=OUT/'line_task_test.c';c.write_text(test,encoding='utf-8');exe=OUT/'line_task_test.exe';cc=ROOT/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe';steps=[]
for args in ([cc,'-Wall','-I'+str(SOURCE),c,SOURCE/'line_task.c','-o',exe],[exe]):
 p=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=30);steps.append(dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));print(p.stdout+p.stderr,end='')
 if p.returncode:raise SystemExit(p.returncode)
(OUT/'task-verification.json').write_text(json.dumps(dict(result='PASS',scope='actual portable C core, controlled inputs only; no physical movement evidence',steps=steps),indent=2),encoding='utf-8')
