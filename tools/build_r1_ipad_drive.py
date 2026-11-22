"""Build-only P7 four-drive overlay. Never flashes hardware or transmits commands."""
from pathlib import Path
import hashlib,json,re,shutil
import build_r1_usbhs_camera_bridge_usb_lifecycle as previous

build=previous.build
BASE=build.PROJECT/'知行回路软件/board/r1_usbhs_camera_bridge_usb_lifecycle'
OVERLAY=build.PROJECT/'知行回路软件/board/r1_ipad_drive'
build.STEM='r1_ipad_drive';build.WORK=build.TOOLS/'r1-ipad-drive';build.OUT=build.PROJECT/'知行回路软件/build/r1_ipad_drive'
build.EXTRA_SOURCES+=[Path('User/remote_drive.c')]
old_prepare=build.PREPARE

def replace(path,old,new):
    text=path.read_text(encoding='utf-8-sig')
    if text.count(old)!=1:raise RuntimeError(f'Overlay base changed: {path.name}: {old[:80]}')
    path.write_text(text.replace(old,new,1),encoding='utf-8')

def prepare():
    old_prepare()
    user=build.WORK/'User'
    # Reuse the separately reviewed ring/DMA reset repair without replacing its
    # original candidate or claiming a physical USB repair.
    recovery=BASE.parent/'r1_usbfs_dma_recovery/usbfs_lifecycle.h'
    shutil.copy2(recovery,user/'usbfs_lifecycle.h')
    for path in OVERLAY.iterdir():
        if path.suffix in ('.h','.c'):shutil.copy2(path,user/path.name)
    replace(user/'main.c','#include "motor_probe.h"','#include "motor_probe.h"\n#include "remote_drive.h"')
    replace(user/'main.c','now=++tick_ms;','now=++tick_ms;\n    remote_drive_tick(now);')
    replace(user/'main.c','motor_probe_poll(tick_ms);','motor_probe_poll(tick_ms);\n        remote_drive_poll(tick_ms);')
    replace(user/'native_usb.c','#include "servo_probe.h"','#include "servo_probe.h"\n#include "remote_drive.h"')
    replace(user/'native_usb.c','if(uvc_bridge_command(command,now,reply))return;',
            'if(remote_drive_command(command,now,reply))return;\n    if(uvc_bridge_command(command,now,reply))return;')
    replace(user/'native_usb.c','reply("NORMAL_USBFS,1\\n")','reply("NORMAL_USBFS,2\\n")')
    replace(user/'native_usb.c','servo_probe_stop();uvc_bridge_stop();',
            'if(remote_drive_armed){remote_drive_stop(3u);}\n        servo_probe_stop();uvc_bridge_stop();')
    replace(user/'native_usb.c','servo_probe_stop();if(camera_link_active)',
            'if(remote_drive_armed){remote_drive_stop(3u);}\n        servo_probe_stop();if(camera_link_active)')
    motor=user/'motor_probe.c'
    replace(motor,'#include "motor_probe.h"','#include "motor_probe.h"\n#include "remote_drive.h"')
    replace(motor,'void motor_stop(void)\n{','void motor_stop(void)\n{\n    if(remote_drive_armed)remote_drive_stop(5u);')
    replace(motor,'static uint8_t stop_repeats,stop_frame;',
'''static uint8_t stop_repeats,stop_frame;
static volatile uint8_t remote_stop_pending,tx_frame_started;
static char remote_frame[48];
void motor_remote_stop_now(void)
{
    remote_stop_pending=3;motor_pulse_active=0;motor_speed_mode=0;
    USART_ITConfig(USART3,USART_IT_TXE,ENABLE);
}
int motor_remote_write(int32_t left,int32_t right)
{
    if(left < -250 || left > 250 || right < -250 || right > 250)return 0;
    // One main-loop writer. UART ISR is excluded while publishing the buffer.
    NVIC_DisableIRQ(USART3_IRQn);
    if(tx || stop_repeats || remote_stop_pending || motor_pulse_active){NVIC_EnableIRQ(USART3_IRQn);return 0;}
    snprintf(remote_frame,sizeof(remote_frame),"$pwm:%ld,%ld,%ld,%ld#",(long)left,(long)left,(long)right,(long)right);
    tx=remote_frame;tx_frame_started=0;
    USART_ITConfig(USART3,USART_IT_TXE,ENABLE);NVIC_EnableIRQ(USART3_IRQn);return 1;
}''')
    # Interrupt-level stop can finish a partially sent line, then emit zero even
    # if the main loop stalls. It cannot stop a driver whose control wire is cut.
    replace(motor,'if(USART_GetITStatus(USART3,USART_IT_TXE)!=RESET){\n        if(tx){',
'''if(USART_GetITStatus(USART3,USART_IT_TXE)!=RESET){
        if(remote_stop_pending && (!tx || !tx_frame_started)){tx="$pwm:0,0,0,0#";stop_frame=1;--remote_stop_pending;}
        if(tx){
            tx_frame_started=1;''')
    replace(motor,'tx=0;USART_ITConfig(USART3,USART_IT_TXE,DISABLE);',
'''tx=0;tx_frame_started=0;
                if(!remote_stop_pending)USART_ITConfig(USART3,USART_IT_TXE,DISABLE);''')
    text=motor.read_text(encoding='utf-8')
    expression=r'(int motor_(?:parameter_write|encoder_upload|pulse_start|startup_hold_start|speed_start|closed_start|calibration_start)\([^{}]*\)\s*\{)'
    text,count=re.subn(expression,r'\1\n    if(remote_drive_armed)return 0;',text)
    if count!=7:raise RuntimeError(f'Unexpected legacy motor entry count: {count}')
    motor.write_text(text,encoding='utf-8')
build.PREPARE=prepare

if __name__=='__main__':
    build.main()
    path=build.OUT/'build_result.json';data=json.loads(path.read_text(encoding='utf-8'))
    data.update(scope='BUILD_ONLY; P7 version2, bounded four-wheel PWM +/-250,600ms fresh-vector lease, TIM2 guard/driver checks, priority USART3 zero, explicit re-arm, BENCH_ONLY',
      physical_acceptance='NOT_RUN',flash='NOT_RUN',ground_drive='NOT_AUTHORIZED_OR_VERIFIED',
      driver_wire_disconnect_stop='KNOWN_UNRESOLVED_PHYSICAL_LIMITATION',
      merged_dma_header_sha256=hashlib.sha256((build.WORK/'User/usbfs_lifecycle.h').read_bytes()).hexdigest(),
      merged_dma_repair='Source-identical to r1_usbfs_dma_recovery header; candidate mock-register evidence only, physical USB not tested',
      overlay_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OVERLAY.iterdir() if p.suffix in ('.c','.h')},
      compiled_user_sources_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (build.WORK/'User').glob('*.c')})
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(path)
