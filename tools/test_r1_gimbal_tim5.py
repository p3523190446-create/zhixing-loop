"""Actual gimbal C with mock register API: pin/timer routing, zero and lease."""
from pathlib import Path
import subprocess,json,hashlib
root=Path(__file__).resolve().parents[2];out=root/'知行回路软件/build/r1_gimbal_tim5';u=out/'source-snapshot';h=out/'host-gimbal-test';h.mkdir(exist_ok=True)
debug=r'''
#include <stdint.h>
#include <assert.h>
typedef struct {uint32_t PSC,ATRLR,CH1CVR,CH2CVR,CCER,CTLR1;} TIM_TypeDef;
typedef struct {uint32_t CFGLR;} GPIO_TypeDef;
typedef struct {uint32_t GPIO_Pin,GPIO_Mode,GPIO_Speed;} GPIO_InitTypeDef;
typedef struct {uint32_t TIM_Prescaler,TIM_Period,TIM_CounterMode,TIM_ClockDivision;} TIM_TimeBaseInitTypeDef;
typedef struct {uint32_t TIM_OCMode,TIM_OutputState,TIM_Pulse,TIM_OCPolarity;} TIM_OCInitTypeDef;
typedef struct {uint32_t PCLK1_Frequency,HCLK_Frequency;} RCC_ClocksTypeDef;
static TIM_TypeDef tim5;static GPIO_TypeDef port_a;
#define TIM5 (&tim5)
#define GPIOA (&port_a)
#define ENABLE 1
#define DISABLE 0
#define GPIO_Pin_0 1
#define GPIO_Pin_1 2
#define GPIO_Mode_AF_PP 2
#define GPIO_Speed_2MHz 2
#define RCC_APB2Periph_GPIOA 4
#define RCC_APB2Periph_AFIO 8
#define RCC_APB1Periph_TIM5 16
#define TIM_CounterMode_Up 0
#define TIM_CKD_DIV1 0
#define TIM_OCMode_PWM1 6
#define TIM_OutputState_Enable 1
#define TIM_OCPolarity_High 0
#define TIM_OCPreload_Enable 1
#define TIM_EventSource_Update 1
#define __disable_irq() ((void)0)
#define __enable_irq() ((void)0)
static uint32_t pin_mask,apb1,apb2;static int divided=1;
static void RCC_APB2PeriphClockCmd(uint32_t b,int e){assert(e);apb2|=b;}
static void RCC_APB1PeriphClockCmd(uint32_t b,int e){assert(e);apb1|=b;}
static void RCC_GetClocksFreq(RCC_ClocksTypeDef *c){c->PCLK1_Frequency=divided?36000000:72000000;c->HCLK_Frequency=72000000;}
static void GPIO_ResetBits(GPIO_TypeDef *g,uint32_t p){assert(g==GPIOA&&p==3);}
static void GPIO_Init(GPIO_TypeDef *g,GPIO_InitTypeDef *p){assert(g==GPIOA&&p->GPIO_Mode==GPIO_Mode_AF_PP&&p->GPIO_Speed==2);pin_mask=p->GPIO_Pin;}
static void TIM_Cmd(TIM_TypeDef *t,int e){assert(t==TIM5);t->CTLR1=e;}
static void TIM_TimeBaseInit(TIM_TypeDef *t,TIM_TimeBaseInitTypeDef *p){assert(t==TIM5);t->PSC=p->TIM_Prescaler;t->ATRLR=p->TIM_Period;}
static void TIM_OC1Init(TIM_TypeDef *t,TIM_OCInitTypeDef *p){assert(t==TIM5);t->CH1CVR=p->TIM_Pulse;t->CCER|=1;}
static void TIM_OC2Init(TIM_TypeDef *t,TIM_OCInitTypeDef *p){assert(t==TIM5);t->CH2CVR=p->TIM_Pulse;t->CCER|=16;}
static void TIM_OC1PreloadConfig(TIM_TypeDef *t,int e){assert(t==TIM5&&e);}
static void TIM_OC2PreloadConfig(TIM_TypeDef *t,int e){assert(t==TIM5&&e);}
static void TIM_ARRPreloadConfig(TIM_TypeDef *t,int e){assert(t==TIM5&&e);}
static void TIM_GenerateEvent(TIM_TypeDef *t,int e){assert(t==TIM5&&e);}
static void TIM_SetCompare1(TIM_TypeDef *t,uint32_t p){assert(t==TIM5);t->CH1CVR=p;}
static void TIM_SetCompare2(TIM_TypeDef *t,uint32_t p){assert(t==TIM5);t->CH2CVR=p;}
'''
(h/'debug.h').write_text(debug,encoding='utf8')
test=r'''
#include <stdio.h>
#include "servo_probe.c"
int main(void){uint32_t n;
 servo_probe_init();assert(pin_mask==3&&apb1==16&&apb2==12);assert(tim5.PSC==71&&tim5.ATRLR==19999&&tim5.CCER==17&&tim5.CTLR1==1);
 assert(state.ready&&state.yaw_hz==1000000&&state.pitch_hz==1000000&&tim5.CH1CVR==0&&tim5.CH2CVR==0);
 assert(servo_probe_manual_start(1000));assert(tim5.CH1CVR==1500&&tim5.CH2CVR==1500);
 assert(!servo_probe_manual_set(1001,999,1500)&&!servo_probe_manual_set(1001,1500,2001));
 assert(servo_probe_manual_set(1001,1600,1400));for(n=1011;n<=2001;n+=10)servo_probe_tick(n);
 assert(tim5.CH1CVR==1600&&tim5.CH2CVR==1400);
 servo_probe_tick(4001);assert(!state.active&&tim5.CH1CVR==0&&tim5.CH2CVR==0&&state.lease_stops==1);
 assert(!servo_probe_keepalive(4002));assert(servo_probe_manual_start(5000));assert(servo_probe_keepalive(7999));servo_probe_tick(8001);assert(state.active);
 servo_probe_stop();assert(!state.active&&tim5.CH1CVR==0&&tim5.CH2CVR==0);
 divided=0;servo_probe_init();assert(tim5.PSC==71&&state.ready&&tim5.CH1CVR==0&&tim5.CH2CVR==0);
 puts("PASS: actual gimbal C PA0/PA1 TIM5 routing, APB clock cases, boot zero, bounds, two-axis targets,3s expiry,keepalive,explicit stop; host mock only");return 0;}
'''
c=h/'test.c';c.write_text(test,encoding='utf8');exe=h/'test.exe';cc=root/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe';steps=[]
for args in [[str(cc),'-Wall','-I'+str(h),'-I'+str(u),str(c),'-o',str(exe)],[str(exe)]]:
 p=subprocess.run(args,capture_output=True,text=True,timeout=20);steps.append(dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));print(p.stdout+p.stderr);assert p.returncode==0,steps
(out/'gimbal-host-verification.json').write_text(json.dumps(dict(result='PASS',scope='Actual gimbal source and mocked peripheral APIs, not physical PWM or movement',source_sha256=hashlib.sha256((u/'servo_probe.c').read_bytes()).hexdigest(),steps=steps),indent=2)+'\n',encoding='utf8')
