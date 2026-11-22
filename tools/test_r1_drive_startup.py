from pathlib import Path
import subprocess,json,hashlib,sys
root=Path(__file__).resolve().parents[2];stem=sys.argv[1] if len(sys.argv)>1 else 'r1_drive_startup';out=root/'知行回路软件/build'/stem;u=out/'source-snapshot'
code=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "wheel_control.c"
#include "remote_drive.c"
volatile uint32_t led_last_good_ms,range_correction_valid,range_corrected_mm,warning_mm;
volatile uint32_t motor_voltage_mv,motor_voltage_last_ms,motor_voltage_frames;
volatile uint32_t motor_speed_frames,motor_speed_last_ms,motor_rx_errors,motor_rx_drops,motor_speed_fault,motor_pulse_active;
volatile int32_t motor_speed_values[4];
static char response[256];static int stops,writes;static int32_t sent[4];
void motor_remote_stop_now(void){stops++;}
int motor_remote_write4(int32_t a,int32_t b,int32_t c,int32_t d){sent[0]=a;sent[1]=b;sent[2]=c;sent[3]=d;writes++;return 1;}
static void reply(const char *s){strcpy(response,s);}
static void cmd(const char *s,uint32_t n){remote_drive_uart_command(s,n,reply);}
static void fresh(uint32_t n){led_last_good_ms=motor_speed_last_ms=motor_voltage_last_ms=n;}
static void reset(uint32_t n){
 remote_drive_stop(5);wheel_control_reset();generation=sequence=0;seen_errors=seen_drops=error_changed_ms=0;
 motor_rx_errors=motor_rx_drops=motor_speed_fault=motor_pulse_active=0;
 memset((void*)motor_speed_values,0,sizeof(motor_speed_values));
 range_correction_valid=1;range_corrected_mm=500;warning_mm=120;motor_voltage_mv=7800;
 motor_speed_frames=motor_voltage_frames=1;fresh(n);
}
int main(void){
 int i;int32_t speeds[4]={0,0,0,0};
 wheel_control_reset();assert(!wheel_control_step(0,0,0,speeds));for(i=0;i<4;i++)assert(wheel_outputs[i]==0);
 wheel_control_step(100,250,250,speeds);for(i=0;i<4;i++){assert(wheel_outputs[i]==375);assert(wheel_targets[i]==120);}
 wheel_control_step(399,250,250,speeds);for(i=0;i<4;i++)assert(wheel_outputs[i]==375);
 speeds[0]=130;speeds[1]=170;speeds[2]=120;speeds[3]=165;
 wheel_control_step(400,250,250,speeds);for(i=0;i<4;i++)assert(wheel_outputs[i]>=0&&wheel_outputs[i]<=375);
 assert(wheel_outputs[0]!=wheel_outputs[1]);
 wheel_control_step(401,20,20,speeds);for(i=0;i<4;i++)assert(wheel_targets[i]==EXPECTED_LOW);
 wheel_control_step(500,0,0,speeds);for(i=0;i<4;i++)assert(wheel_outputs[i]==0);
 wheel_control_reset();memset(speeds,0,sizeof(speeds));wheel_control_step(0,250,250,speeds);
 for(i=100;i<1000;i+=100)assert(!wheel_control_step(i,250,250,speeds));
 assert(wheel_control_step(1000,250,250,speeds)==1);for(i=0;i<4;i++)assert(!wheel_outputs[i]);
 assert(wheel_control_step(1100,250,250,speeds)==1); /* no automatic restart */
 wheel_control_reset();wheel_control_step(0,250,250,speeds);speeds[0]=321;
 assert(wheel_control_step(10,250,250,speeds)==17);for(i=0;i<4;i++)assert(!wheel_outputs[i]);
 wheel_control_reset();memset(speeds,0,sizeof(speeds));wheel_control_step(0,250,250,speeds);speeds[2]=-30;
 assert(wheel_control_step(300,250,250,speeds)==35);
 wheel_control_reset();memset(speeds,0,sizeof(speeds));wheel_control_step(0,250,250,speeds);
 speeds[0]=30;wheel_control_step(400,-250,250,speeds);assert(wheel_outputs[0]==0);
 speeds[0]=0;wheel_control_step(549,-250,250,speeds);assert(wheel_outputs[0]==0);
 wheel_control_step(550,-250,250,speeds);assert(wheel_outputs[0]==-375);
 wheel_control_reset();memset(speeds,0,sizeof(speeds));wheel_control_step(0xffffff00u,250,250,speeds);
 wheel_control_step(0x20u,250,250,speeds);assert(wheel_outputs[0]==375);
 reset(2000);cmd("DRIVE_ARM",2000);assert(remote_drive_armed);cmd("DRIVE_SET,1,1,250,250",2001);remote_drive_poll(2021);assert(sent[0]==375&&sent[3]==375);
 cmd("DRIVE_SET,1,1,0,0",2022);assert(!strcmp(response,"ERR,DRIVE_REJECTED\n"));assert(desired_left==250);
 cmd("DRIVE_SET,1,2,251,250",2023);assert(!strcmp(response,"ERR,DRIVE_REJECTED\n"));
 cmd("DRIVE_BRAKE,1,2",2024);assert(remote_drive_armed&&!remote_drive_moving);for(i=0;i<4;i++)assert(!wheel_outputs[i]);
 fresh(2624);remote_drive_tick(2624);assert(!remote_drive_armed&&reason==1);
 reset(3000);range_corrected_mm=120;cmd("DRIVE_ARM",3000);assert(!remote_drive_armed);
 reset(3000);led_last_good_ms=2700;cmd("DRIVE_ARM",3000);assert(!remote_drive_armed);
 reset(3000);motor_voltage_mv=5999;cmd("DRIVE_ARM",3000);assert(!remote_drive_armed);
 reset(3000);motor_voltage_mv=8501;cmd("DRIVE_ARM",3000);assert(!remote_drive_armed);
 reset(3000);cmd("DRIVE_ARM",3000);motor_rx_errors=1;remote_drive_tick(3001);assert(!remote_drive_armed&&reason==4);
 reset(3000);cmd("DRIVE_ARM",3000);cmd("DRIVE_SET,1,1,250,250",3001);for(i=3021;i<4100&&remote_drive_armed;i+=20){fresh(i);last_set=i;remote_drive_poll(i);}assert(!remote_drive_armed&&reason==7&&wheel_fault==1);
 reset(5000);remote_drive_command("DRIVE_ARM",5000,reply);assert(remote_drive_armed&&!remote_drive_uart_owner);remote_drive_stop(3);assert(!remote_drive_armed);
 puts("PASS: startup duration/bounds, per-wheel feedback, low target, zero, stall latch, overspeed, reverse feedback, brake before reversing, timer wrap, plus protocol generation/sequence/range/voltage/UART/lease/USB and whole-drive stall stop");
 return 0;
}
'''
manual='_manual_' in stem
code=code.replace('EXPECTED_LOW','83' if ('_stable' in stem or manual) else '40')
if manual:
 code=code.replace('reset(3000);range_corrected_mm=120;cmd("DRIVE_ARM",3000);assert(!remote_drive_armed);', '''reset(3000);range_corrected_mm=1;cmd("DRIVE_ARM",3000);assert(remote_drive_armed);
 cmd("DRIVE_SET,1,1,-100,100",3001);remote_drive_poll(3021);assert(sent[0]<0&&sent[1]<0&&sent[2]>0&&sent[3]>0);
 range_correction_valid=0;range_corrected_mm=0xffffffffu;led_last_good_ms=0;fresh(3041);led_last_good_ms=0;
 cmd("DRIVE_SET,1,2,100,-100",3041);remote_drive_tick(3042);assert(remote_drive_armed&&blocked(3042)==0);''')
 code=code.replace('reset(3000);led_last_good_ms=2700;cmd("DRIVE_ARM",3000);assert(!remote_drive_armed);','reset(3000);range_correction_valid=0;led_last_good_ms=0;cmd("DRIVE_ARM",3000);assert(remote_drive_armed);')
 code=code.replace(' puts("PASS:', ''' /* Both pivots, arcs and reverse arcs preserve left/right signs and ratios. */
 {int32_t vectors[8][2]={{250,250},{-250,-250},{-250,250},{250,-250},{50,250},{250,50},{-250,-50},{-50,-250}};
 for(int v=0;v<8;v++){
   wheel_control_reset();memset(speeds,0,sizeof(speeds));wheel_control_step(0,vectors[v][0],vectors[v][1],speeds);
   for(i=0;i<4;i++){int32_t input=vectors[v][i<2?0:1];assert((wheel_outputs[i]>0)==(input>0));assert(absolute(wheel_outputs[i])<=375);assert((wheel_targets[i]>0)==(input>0));speeds[i]=wheel_targets[i];}
   if(v>=4){int a=absolute(wheel_targets[0]),b=absolute(wheel_targets[2]);assert((a>b?a:b)==120);assert((a<b?a:b)==24);assert(absolute(wheel_outputs[a<b?0:2])==75);}
   wheel_control_step(300,vectors[v][0],vectors[v][1],speeds);assert(!wheel_fault);
   wheel_control_step(320,0,0,speeds);for(i=0;i<4;i++)assert(wheel_outputs[i]==0);
 }}
 reset(5000);motor_speed_last_ms=4400;cmd("DRIVE_ARM",5000);assert(!remote_drive_armed);
 reset(5000);motor_voltage_last_ms=2500;cmd("DRIVE_ARM",5000);assert(!remote_drive_armed);
 puts("PASS: manual near/stale/invalid range advisory, both pivots/arcs/reverse arcs, retained driver freshness; ''')
if stem.endswith('_v4'):
 code=code.replace('wheel_control_step(399,','wheel_control_step(299,').replace('wheel_control_step(400,250,250,speeds);for','wheel_control_step(300,250,250,speeds);for')
 code=code.replace('375','600').replace('wheel_outputs[i]<=600','wheel_outputs[i]<=900').replace('wheel_control_step(0x20u,','wheel_control_step(0xffffff80u,')
 code=code.replace('{50,250},{250,50},{-250,-50},{-50,-250}','{150,250},{250,150},{-250,-150},{-150,-250}')
 code=code.replace('(a<b?a:b)==24','(a<b?a:b)==72').replace('absolute(wheel_outputs[a<b?0:2])==75','absolute(wheel_outputs[a<b?0:2])==600')
 code=code.replace(' puts("PASS:',r''' wheel_control_reset();memset(speeds,0,sizeof(speeds));wheel_control_step(0,20,250,speeds);
 assert(wheel_targets[0]==0&&wheel_outputs[0]==0&&wheel_targets[2]==120&&wheel_outputs[2]==600);
 speeds[0]=speeds[1]=40;wheel_control_step(20,150,250,speeds);assert(wheel_outputs[0]>0&&wheel_outputs[1]>0);
 wheel_control_reset();speeds[0]=speeds[1]=-40;wheel_control_step(0,250,250,speeds);assert(wheel_outputs[0]==0&&wheel_outputs[1]==0);
 assert(wheel_control_step(820,250,250,speeds)==49);
 /* A simple inertial plant is injected feedback, not hardware calibration.
  *550PWM stiction makes old375 unable to move; load900 bound can regulate120. */
 {double velocity[4]={0,0,0,0};int32_t pwm;int n,j;int loads[4]={550,480,520,500};
  wheel_control_reset();memset(speeds,0,sizeof(speeds));
  for(n=0;n<=6000;n+=20){
   assert(!wheel_control_step(n,-250,250,speeds));
   for(j=0;j<4;j++){
    pwm=wheel_outputs[j];assert(absolute(pwm)<=900);
    double ideal=(absolute(pwm)>loads[j]?(absolute(pwm)-loads[j])/2.0:0)*(pwm<0?-1:1);
    velocity[j]+=(ideal-velocity[j])*.12;speeds[j]=(int32_t)velocity[j];
   }
  }
  for(j=0;j<4;j++)assert(absolute(speeds[j])>=105&&absolute(speeds[j])<=135);
  wheel_control_step(6020,0,0,speeds);for(j=0;j<4;j++)assert(wheel_outputs[j]==0);
 }
 puts("PASS: loaded candidate cap900/start600200ms, inner coast, injected high-load pivot regulation; ''')
c=out/'startup-control-test.c';c.write_text(code,encoding='utf8');exe=out/'startup-control-test.exe'
compiler=root/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe';steps=[]
for args in [[str(compiler),'-Wall','-I'+str(u),str(c),'-o',str(exe)],[str(exe)]]:
 p=subprocess.run(args,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=20);steps.append(dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));print(p.stdout+p.stderr);assert p.returncode==0,steps
(out/'controller-host-verification.json').write_text(json.dumps(dict(result='PASS',scope='Actual C state machine with injected driver feedback; not hardware evidence',steps=steps,source_sha256={n:hashlib.sha256((u/n).read_bytes()).hexdigest() for n in ['wheel_control.c','remote_drive.c']}),indent=2)+'\n',encoding='utf8')
