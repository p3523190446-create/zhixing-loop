"""Fixed-point voltage, stale-data boundaries and actual OLED framebuffer check; no hardware."""
from pathlib import Path
import json, shutil, subprocess
from PIL import Image

root=Path(__file__).resolve().parents[2]
src=root/'知行回路软件/board/r1_motor_dashboard'
out=root/'知行回路软件/build/r1_motor_dashboard/host-check'
out.mkdir(parents=True,exist_ok=True)
for name in ('motor_probe.h','motor_telemetry.h','oled_display2.c','oled_display2.h','oled_probe2.h','oled_glyphs.h'):
    shutil.copy2(src/name,out/name)
(out/'debug.h').write_text('#include <stdint.h>\n',encoding='utf-8')
(out/'guard.h').write_text('',encoding='utf-8')
code=r'''
#include <assert.h>
#include <stdio.h>
#include "oled_display2.c"
volatile uint32_t oled2_ack_3c,oled2_ack_3d;
volatile uint32_t motor_voltage_mv,motor_voltage_last_ms,motor_voltage_frames,motor_monitor_enabled;
volatile uint32_t motor_encoder_upload_enabled,motor_speed_frames,motor_speed_last_ms;
volatile uint32_t motor_pulse_active,motor_fault_cause,motor_rx_errors,motor_rx_drops;
volatile int32_t motor_speed_values[4];
uint8_t oled2_bus_write(uint8_t a,uint8_t c,const uint8_t *p,unsigned n){return 1;}
static void dump(const char *name){FILE *f=fopen(name,"wb");assert(f);assert(fwrite(image,1,1024,f)==1024);fclose(f);}
int main(void){
    uint32_t mv=999;unsigned i;int32_t speeds[]={0,0,0,0};
    const char *invalid[]={"$Battery:8.2V#junk","$Battery:8.0000V#","$Battery:-8.2V#","$Battery:nanV#",
        "$Battery:8.V#","$Battery:.2V#","$Battery:99999999999.0V#","$Battery:20.001V#","$MSPD:8.2V#"};
    assert(motor_parse_voltage("$Battery:8.2V#",&mv) && mv==8200);
    assert(motor_parse_voltage("$Battery:8.21V#",&mv) && mv==8210);
    assert(motor_parse_voltage("$Battery:8.005V#",&mv) && mv==8005);
    assert(motor_parse_voltage("$Battery:6.0V#",&mv) && mv==6000);
    for(i=0;i<sizeof(invalid)/sizeof(invalid[0]);i++){mv=999;assert(!motor_parse_voltage(invalid[i],&mv) && mv==999);}
    assert(!motor_value_fresh(0,0,0,500));assert(motor_value_fresh(500,0,1,500));
    assert(!motor_value_fresh(501,0,1,500));assert(motor_value_fresh(50,0xfffffff0u,1,500));
    assert(motor_dashboard_state(0,speeds,0,0,0,0,1,8200)==0);
    assert(motor_dashboard_state(1,speeds,0,0,0,0,1,8200)==1);
    speeds[2]=120;assert(motor_dashboard_state(1,speeds,0,0,0,0,1,8200)==2);
    assert(motor_dashboard_state(1,speeds,0,4,0,0,1,8200)==3);
    assert(motor_dashboard_state(1,speeds,0,0,1,0,1,8200)==3);
    assert(motor_dashboard_state(1,speeds,0,0,0,0,1,5900)==3);
    /* Actual renderer at idle, signed speed extremes, offline and latched fault. */
    motor_voltage_mv=8210;motor_voltage_last_ms=1000;motor_voltage_frames=1;
    motor_encoder_upload_enabled=1;motor_speed_frames=1;motor_speed_last_ms=1000;
    compose(1000);dump("idle.bin");
    motor_speed_values[0]=-2000;motor_speed_values[1]=2000;motor_speed_values[2]=120;motor_speed_values[3]=-999;
    compose(1000);dump("moving.bin");
    compose(5001);dump("offline.bin");
    motor_fault_cause=4;compose(1000);dump("fault.bin");
    puts("VOLTAGE_STALENESS_STATE_AND_RENDER_PASS");return 0;
}
'''
(out/'check.c').write_text(code,encoding='utf-8')
tcc=root/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe'
subprocess.run([str(tcc),'-o',str(out/'check.exe'),str(out/'check.c')],check=True,cwd=out)
r=subprocess.run([str(out/'check.exe')],cwd=out,check=True,capture_output=True,text=True)
canvas=Image.new('RGB',(128*4,64*4*4),(40,40,40))
for i,name in enumerate(('idle','moving','offline','fault')):
    data=(out/(name+'.bin')).read_bytes();im=Image.new('RGB',(128,64))
    for y in range(64):
        for x in range(128):
            if data[(y//8)*128+x]&(1<<(y%8)):im.putpixel((x,y),(220,250,255))
    canvas.paste(im.resize((512,256),Image.Resampling.NEAREST),(0,i*256))
canvas.save(out/'preview.png')
(out/'result.json').write_text(json.dumps({'result':r.stdout.strip(),'hardware_access':'NONE',
    'cases':['voltage 1/2/3 decimal digits','malformed packet rejection','stale at 501ms','timer wrap',
             'idle/moving/offline/fault rendering','signed speed -2000..2000']},indent=2)+'\n',encoding='utf-8')
print(r.stdout.strip())
