"""Run actual MCU control sources and Android broker against fake IO only."""
from pathlib import Path
import json,subprocess
ROOT=Path(__file__).resolve().parents[2];SW=ROOT/'知行回路软件'
SRC=SW/'board/r1_mecanum';BASE=SW/'build/r1_imu_observer/source-snapshot'
OUT=ROOT/'output/onboard_dashboard/mecanum-20261026/checks';OUT.mkdir(parents=True,exist_ok=True)

C=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "remote_drive.h"
#include "motor_probe.h"
#include "wheel_control.h"
#include "mecanum_mix.h"
static unsigned checks,stops,writes;
#define CHECK(x) do{++checks;if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
volatile uint32_t led_last_good_ms,range_correction_valid,range_corrected_mm,warning_mm;
volatile uint32_t motor_profile_ready,motor_rx_errors,motor_rx_drops;
volatile uint32_t motor_voltage_mv,motor_voltage_frames,motor_voltage_last_ms;
volatile uint32_t motor_speed_frames,motor_speed_last_ms,motor_speed_fault,motor_pulse_active;
volatile int32_t motor_speed_values[4];driver_profile_t motor_profile;
int motor_remote_write4(int32_t a,int32_t b,int32_t c,int32_t d){++writes;return 1;}
void motor_remote_stop_now(void){++stops;}
static char response[256];
static void reply(const char*s){strcpy(response,s);}
static void command(const char*s,uint32_t now){response[0]=0;CHECK(remote_drive_command(s,now,reply)==1);}
static void healthy(uint32_t now){motor_voltage_mv=7400;motor_voltage_frames=motor_speed_frames=1;motor_voltage_last_ms=motor_speed_last_ms=now;motor_speed_fault=0;motor_profile_ready=1;}
static void expected(int f,int x,int r,int a,int b,int c,int d){int32_t out[4];CHECK(mecanum_mix(f,x,r,out));CHECK(out[0]==a&&out[1]==b&&out[2]==c&&out[3]==d);}
int main(void){
 int f,x,r,i;int32_t out[4];unsigned prev;char q[100];uint32_t now;
 expected(0,0,0,0,0,0,0);expected(250,0,0,250,250,250,250);expected(-250,0,0,-250,-250,-250,-250);
 expected(0,250,0,250,-250,-250,250);expected(0,-250,0,-250,250,250,-250);
 expected(0,0,250,250,250,-250,-250);expected(0,0,-250,-250,-250,250,250);
 expected(250,250,0,250,0,0,250);expected(250,-250,0,0,250,250,0);
 expected(-250,250,0,0,-250,-250,0);expected(-250,-250,0,-250,0,0,-250);
 expected(250,250,250,250,83,-83,83);
 for(f=-250;f<=250;f+=25)for(x=-250;x<=250;x+=25)for(r=-250;r<=250;r+=25){
  CHECK(mecanum_mix(f,x,r,out));for(i=0;i<4;i++)CHECK(out[i]>=-250&&out[i]<=250);
  CHECK(mecanum_mix(-f,-x,-r,out));
 }
 out[0]=123;CHECK(!mecanum_mix(251,0,0,out)&&out[0]==123);CHECK(!mecanum_mix(0,INT32_MIN,0,out));CHECK(!mecanum_mix(0,0,INT32_MAX,out));
 healthy(2000);motor_profile_ready=0;command("DRIVE_ARM",2000);CHECK(!remote_drive_armed&&!strcmp(response,"ERR,DRIVE_NOT_READY\n"));
 healthy(2000);command("DRIVE_ARM",2000);CHECK(!strcmp(response,"DRIVE_ARMED,1\n")&&remote_drive_armed&&!remote_drive_moving);
 command("DRIVE_VECTOR,1,1,0,100,0",2020);CHECK(!strcmp(response,"DRIVE_VECTOR_ACCEPTED\n"));healthy(2020);remote_drive_poll(2020);
 CHECK(wheel_targets[0]==400&&wheel_targets[1]==-400&&wheel_targets[2]==-400&&wheel_targets[3]==400);
 command("DRIVE_VECTOR,1,1,100,0,0",2030);CHECK(!strcmp(response,"ERR,DRIVE_REJECTED\n"));
 command("DRIVE_VECTOR,2,2,100,0,0",2040);CHECK(!strcmp(response,"ERR,DRIVE_REJECTED\n"));
 {const char*bad[]={"DRIVE_VECTOR,1,2,251,0,0","DRIVE_VECTOR,1,2,1,0,0,0","DRIVE_VECTOR,1,2,1,,0","DRIVE_VECTOR,1,2,+1,0,0","DRIVE_VECTOR,1,2147483648,1,0,0","DRIVE_SET,1,2,1,1","DRIVE_VECTOR,1,0,1,0,0","DRIVE_VECTOR,1,2,1,0,","DRIVE_VECTOR,1,2,1,0,0x"};
  for(i=0;i<9;i++){command(bad[i],2050);CHECK(!strcmp(response,"ERR,DRIVE_REJECTED\n"));}}
 command("DRIVE_VECTOR,1,2,100,100,0",2100);CHECK(!strcmp(response,"DRIVE_VECTOR_ACCEPTED\n"));
 command("DRIVE_BRAKE,1,3",2120);CHECK(!strcmp(response,"DRIVE_BRAKED\n")&&remote_drive_armed&&!remote_drive_moving);
 command("DRIVE_VECTOR_STATUS",2120);CHECK(!strcmp(response,"DRIVE_VECTOR,0,0,0,0,0,0,0\n"));
 for(i=0;i<4;i++)CHECK(wheel_outputs[i]==0&&wheel_targets[i]==0);
 command("DRIVE_VECTOR,1,2,100,0,0",2200);CHECK(!strcmp(response,"ERR,DRIVE_REJECTED\n"));
 healthy(2719);remote_drive_tick(2719);CHECK(remote_drive_armed);healthy(2720);remote_drive_tick(2720);CHECK(!remote_drive_armed); // rejected messages never renew lease
 command("DRIVE_ARM",3000);CHECK(!strcmp(response,"DRIVE_ARMED,2\n"));command("DRIVE_VECTOR,1,4,100,0,0",3000);CHECK(!strcmp(response,"ERR,DRIVE_REJECTED\n"));
 healthy(3000);motor_voltage_mv=5000;remote_drive_tick(3000);CHECK(!remote_drive_armed);
 healthy(4000);command("DRIVE_ARM",4000);command("DRIVE_VECTOR,3,1,50,0,0",4000);
 for(now=4020,i=2;now<5200&&remote_drive_armed;now+=20,++i){healthy(now);snprintf(q,sizeof(q),"DRIVE_VECTOR,3,%d,50,0,0",i);command(q,now);remote_drive_poll(now);}
 CHECK(!remote_drive_armed&&wheel_fault==1);for(i=0;i<4;i++)CHECK(wheel_outputs[i]==0);
 healthy(6000);command("DRIVE_ARM",6000);motor_rx_errors=1;remote_drive_tick(6000);CHECK(!remote_drive_armed);
 healthy(8000);command("DRIVE_ARM",8000);CHECK(remote_drive_armed);remote_drive_stop(3);CHECK(!remote_drive_armed&&!remote_drive_uart_owner);
 // Reversal holds zero until wheel feedback is stopped and brake dwell expires.
 {int32_t inputs[4]={100,100,100,100};wheel_control_reset();memset((void*)motor_speed_values,0,sizeof(motor_speed_values));CHECK(!wheel_control_step4(9000,inputs,motor_speed_values));
  for(i=0;i<4;i++){inputs[i]=-100;motor_speed_values[i]=30;}CHECK(!wheel_control_step4(9020,inputs,motor_speed_values));for(i=0;i<4;i++)CHECK(wheel_outputs[i]==0);
  memset((void*)motor_speed_values,0,sizeof(motor_speed_values));CHECK(!wheel_control_step4(9100,inputs,motor_speed_values));CHECK(wheel_outputs[0]==0);
  CHECK(!wheel_control_step4(9180,inputs,motor_speed_values));CHECK(wheel_outputs[0]<0);
  motor_speed_values[2]=1251;CHECK(wheel_control_step4(9200,inputs,motor_speed_values)==19);for(i=0;i<4;i++)CHECK(wheel_outputs[i]==0);}
 motor_rx_errors=1;healthy(0xffffff00u);command("DRIVE_ARM",0xffffff00u);CHECK(remote_drive_armed);healthy(0x157u);remote_drive_tick(0x157u);CHECK(remote_drive_armed);healthy(0x158u);remote_drive_tick(0x158u);CHECK(!remote_drive_armed);
 CHECK(stops>0&&writes>0);
 printf("{\"result\":\"PASS\",\"assertions\":%u,\"hardware_io\":false}\n",checks);return 0;
}
'''

JAVA=r'''
import cn.zhixing.dashboard.*;import org.json.*;import java.util.*;import java.util.concurrent.*;
public class MecanumHarness {
 static int checks;static void ck(boolean x){checks++;if(!x)throw new AssertionError("check "+checks);}
 static boolean armed;static long generation;static List<String> sent=new ArrayList<>();
 static ControlBroker.Exchange link=(command,prefix)->{
   sent.add(command);if(command.equals("DRIVE_ARM")){armed=true;generation++;return "DRIVE_ARMED,"+generation;}
   if(command.equals("DRIVE_STOP"))armed=false;
   if(command.equals("DRIVE_STATUS"))return "DRIVE,1000,"+(armed?1:0)+",0,"+generation+",0,0,0,0,0";
   return prefix;
 };
 static JSONObject run(DriveBroker b,String action,JSONObject body)throws Exception{
   CompletableFuture<JSONObject> task=CompletableFuture.supplyAsync(()->{try{return b.submit(action,body);}catch(Exception e){throw new CompletionException(e);}});
   long until=System.currentTimeMillis()+2500;while(!task.isDone()&&System.currentTimeMillis()<until){b.pump(link);Thread.sleep(1);}return task.get(1,TimeUnit.SECONDS);
 }
 static JSONObject vector(String sid,int seq,int f,int x,int r,int limit)throws Exception{return new JSONObject().put("session",sid).put("seq",seq).put("throttle",f).put("strafe",x).put("turn",r).put("limit",limit);}
 public static void main(String[] args)throws Exception{
   DriveBroker b=new DriveBroker();b.setMecanum(true);String sid=run(b,"start",new JSONObject().put("mode","manual")).getString("session");
   run(b,"set",vector(sid,1,0,100,0,20));ck(sent.get(sent.size()-1).equals("DRIVE_VECTOR,1,1,0,50,0"));
   run(b,"set",vector(sid,2,100,100,100,20));ck(sent.get(sent.size()-1).equals("DRIVE_VECTOR,1,2,16,16,16"));
   run(b,"set",vector(sid,3,0,0,-100,100));ck(sent.get(sent.size()-1).equals("DRIVE_VECTOR,1,3,0,0,-250"));
   int n=sent.size();try{run(b,"set",vector(sid,2,100,0,0,20));throw new AssertionError();}catch(ExecutionException expected){}ck(sent.size()==n);
   try{b.submit("set",vector(sid,4,0,101,0,20));throw new AssertionError();}catch(IllegalArgumentException expected){}ck(sent.size()==n);
   try{b.submit("set",vector(sid,4,0,0,0,20).put("strafe",true));throw new AssertionError();}catch(IllegalArgumentException expected){}ck(sent.size()==n);
   try{b.submit("set",vector(sid,4,0,0,0,20).put("strafe",1.0));throw new AssertionError();}catch(IllegalArgumentException expected){}ck(sent.size()==n);
   run(b,"brake",new JSONObject().put("session",sid).put("seq",5));ck(sent.get(sent.size()-1).equals("DRIVE_BRAKE,1,5"));
   ck(b.publicState().getBoolean("active"));b.observe("DRIVE,1001,0,0,1,5,0,0,1,600");ck(!b.publicState().getBoolean("active"));
   ck(b.publicState().getString("chassis").equals("mecanum"));ck(b.publicState().getInt("protocol_version")==5);
   b.disconnect();b.setMecanum(false);armed=false;sid=run(b,"start",new JSONObject().put("mode","manual")).getString("session");
   run(b,"set",vector(sid,1,100,0,0,100));ck(sent.get(sent.size()-1).equals("DRIVE_SET,2,1,250,250"));
   n=sent.size();try{b.submit("set",vector(sid,2,0,100,0,20));throw new AssertionError();}catch(IllegalArgumentException expected){}ck(sent.size()==n);
   run(b,"stop",new JSONObject());ck(!b.publicState().getBoolean("active"));b.setMecanum(false);
   ck(BoardReplyException.rejects("DRIVE_VECTOR,1,1,0,0,0","ERR,DRIVE_REJECTED"));
   ck(!BoardReplyException.rejects("DRIVE_STATUS","ERR,OTHER"));
   System.out.println("{\"result\":\"PASS\",\"assertions\":"+checks+",\"hardware_io\":false}");
 }
}
'''

def main():
    c=OUT/'mecanum_harness.c';c.write_text(C,encoding='utf-8');exe=OUT/'mecanum_harness.exe'
    cc=ROOT/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe'
    subprocess.run([str(cc),'-I'+str(SRC),'-I'+str(BASE),str(c),str(SRC/'remote_drive.c'),str(SRC/'wheel_control.c'),str(SRC/'mecanum_mix.c'),'-o',str(exe)],check=True)
    result=subprocess.run([str(exe)],capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    report={'mcu_host':json.loads(result.stdout)}
    work=OUT/'jvm';work.mkdir(exist_ok=True)
    stub=work/'SystemClock.java';stub.write_text('package android.os; public final class SystemClock {public static long elapsedRealtime(){return System.nanoTime()/1000000;}}',encoding='utf-8')
    harness=work/'MecanumHarness.java';harness.write_text(JAVA,encoding='utf-8')
    java=Path('C:/Program Files/BellSoft/LibericaJDK-17/bin');jar=ROOT/'tmp/realtime-harness/json.jar';ui=SW/'debug_ui_mecanum/android'
    subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-cp',str(jar),'-d',str(work),str(stub),str(ui/'ControlBroker.java'),str(ui/'DriveBroker.java'),str(ui/'BoardReplyException.java'),str(harness)],check=True)
    result=subprocess.run([str(java/'java.exe'),'-cp',str(work)+';'+str(jar),'MecanumHarness'],capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    report['android_jvm']=json.loads(result.stdout)
    (OUT/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))

if __name__=='__main__':main()
