"""Build a bounded line-task execution overlay. No flashing or device access."""
from pathlib import Path
import hashlib,json,shutil
import build_r1_imu_observer as previous
build=previous.build
BASE=build.PROJECT/'知行回路软件/build/r1_imu_observer/source-snapshot'
OVERLAY=build.PROJECT/'知行回路软件/board/r1_line_task'
base_prepare=build.PREPARE
build.STEM='r1_line_task';build.WORK=build.TOOLS/'r1-line-task';build.OUT=build.PROJECT/'知行回路软件/build/r1_line_task'
build.EXTRA_SOURCES += [Path('User/line_task.c'),Path('User/line_task_runtime.c')]
def edit(p,old,new):
 s=p.read_text(encoding='utf-8-sig');assert s.count(old)==1,(p,old[:70]);p.write_text(s.replace(old,new),encoding='utf-8')
def prepare():
 base_prepare();u=build.WORK/'User';shutil.copytree(BASE,u,dirs_exist_ok=True)
 for p in OVERLAY.iterdir():
  if p.suffix in ('.c','.h'):shutil.copy2(p,u/p.name)
 edit(u/'line_tracking.h','#include <stdint.h>','#include <stdint.h>\n#include "line_task.h"\nvoid line_tracking_task_input(uint32_t now,lt_input *out);')
 with (u/'line_tracking.c').open('a',encoding='utf-8') as f:f.write('''
void line_tracking_task_input(uint32_t now,lt_input *p){
 unsigned i;memset(p,0,sizeof(*p));
 for(i=0;i<8;i++){p->raw[i]=data.analog[i];p->white_mask|=(uint8_t)(data.digital[i]<<i);}
 p->analog_frames=data.analog_frames;p->digital_frames=data.digital_frames;
 p->analog_age=(uint32_t)(now-data.analog_ms);p->digital_age=(uint32_t)(now-data.digital_ms);
 p->valid=(uint8_t)(data.analog_frames&&data.digital_frames&&seen_errors==uart_errors&&seen_overflows==overflows);
}
''')
 edit(u/'main.c','#include "line_tracking.h"','#include "line_tracking.h"\n#include "line_task_runtime.h"')
 edit(u/'main.c','        remote_drive_poll(tick_ms);','        line_task_poll(tick_ms);\n        remote_drive_poll(tick_ms);')
 edit(u/'vision_uart.c','#include "line_tracking.h"','#include "line_tracking.h"\n#include "line_task_runtime.h"')
 edit(u/'vision_uart.c','    if(line_tracking_command(line,now,reply))return;','    if(line_task_command(line,now,reply))return;\n    if(line_tracking_command(line,now,reply))return;')
 # Explicit task commands share the normal P7 dispatcher; no automatic start.
 edit(u/'native_usb.c','#include "remote_drive.h"','#include "remote_drive.h"\n#include "line_task_runtime.h"')
 # A complete 16-value profile can exceed the original 95-byte command limit.
 edit(u/'native_usb.c','static char command[96]','static char command[192]')
 edit(u/'vision_uart.c','static char line[96]','static char line[192]')
 edit(u/'native_usb.c','    if(remote_drive_command(command,now,reply))return;','    if(line_task_usb_command(command,now,reply))return;\n    if(remote_drive_command(command,now,reply))return;')
 edit(u/'vision_uart.c','        "MPU_FEATURES_ID","MPU_FEATURES",','        "LINE_TASK_CAPS","LINE_TASK_STATUS",\n        "MPU_FEATURES_ID","MPU_FEATURES",')
 edit(u/'remote_drive.c','#include "remote_drive.h"','#include "remote_drive.h"\n#include "line_task_runtime.h"')
 helper='''
static int task_accepted;
static void task_reply(const char *r){task_accepted=!strncmp(r,"DRIVE_ARMED,",12)||!strcmp(r,"DRIVE_SET_ACCEPTED\\n");}
int remote_drive_task_begin(uint32_t now,int uart_owner){
 task_accepted=0;remote_drive_uart_owner=(uint32_t)uart_owner;remote_drive_common("DRIVE_ARM",now,task_reply);return task_accepted;
}
int remote_drive_task_set(uint32_t now,int left,int right){
 char c[96];task_accepted=0;
 if(left < -100||left > 100||right < -100||right > 100)return 0;
 snprintf(c,sizeof(c),"DRIVE_SET,%lu,%lu,%d,%d",(unsigned long)generation,(unsigned long)(sequence+1),left,right);
 remote_drive_common(c,now,task_reply);return task_accepted;
}
'''
 edit(u/'remote_drive.c','int remote_drive_command(const char *c,uint32_t n,void (*r)(const char *))',helper+'\nint remote_drive_command(const char *c,uint32_t n,void (*r)(const char *))')
 for name in ('remote_drive_command','remote_drive_uart_command'):
  anchor='int '+name+'(const char *c,uint32_t n,void (*r)(const char *))\n{'
  edit(u/'remote_drive.c',anchor,anchor+'if(line_task_running()&&(!strcmp(c,"DRIVE_ARM")||!strncmp(c,"DRIVE_SET,",10)||!strncmp(c,"DRIVE_BRAKE,",12))){r("ERR,LINE_TASK_OWNS_DRIVE\\n");return 1;}')
build.PREPARE=prepare
if __name__=='__main__':
 build.main();snap=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snap,dirs_exist_ok=True)
 changed=sorted(p.relative_to(snap).as_posix() for p in snap.rglob('*') if p.is_file() and (not (BASE/p.relative_to(snap)).exists() or p.read_bytes()!=(BASE/p.relative_to(snap)).read_bytes()))
 p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf-8'))
 d.update(date='2026-10-26',scope='50Hz MCU line task with explicit P7/P9 commands, bounded PD, stale/lost/guard stop',changed_sources_vs_deployed_imu=changed,
   ground_permission=False,physical_acceptance='NOT_RUN',flash='NOT_RUN',phone_execution='CAPABILITY_GATED_START_STOP_HEARTBEAT; device acceptance separate',
   all_source_sha256={x.relative_to(snap).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snap.rglob('*') if x.is_file()})
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
