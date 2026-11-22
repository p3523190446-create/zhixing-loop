#include "debug.h"
#include "motor_probe.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>
#include <math.h>

/* Bench diagnostic: nonzero PWM only on explicit fixed-channel test command; persistent driver changes only through four fixed TT parameter commands.
 * USART3 full remap: PD8 TX -> module RX2, PD9 RX <- module TX2.
 * Each boot releases PID with zero PWM, then queries battery voltage.
 * Bounded RX/TX servicing preserves ToF, three OLEDs and timer service. */
volatile uint32_t motor_rx_bytes,motor_rx_errors,motor_rx_drops;
volatile uint32_t motor_queries,motor_tx_bytes,motor_log_count,motor_last_rx_ms;
volatile uint8_t motor_log[128];
static volatile uint8_t rx[2048];
static volatile uint32_t rx_head,rx_tail;
static const char * volatile tx;
static uint32_t last_query_ms;
static uint8_t zero_sent,query_started;
volatile uint32_t motor_pulse_active,motor_pulse_count,motor_pulse_stops,motor_pulse_started_ms,motor_pulse_stopped_ms;
static uint8_t stop_repeats,stop_frame;
extern volatile uint32_t tick_ms;
volatile int32_t motor_control_speed,motor_control_pwm;
volatile uint32_t motor_control_updates;
static int32_t control_prev_count,control_integral_q8,control_filtered_q8;
static uint32_t control_last_ms;
static uint8_t overspeed_streak;
static char control_command[40];
static const int32_t control_feedforward[]={232,163,224,173};
static uint8_t closed_kick_pending;
static uint32_t motion_deadline_ms=250u,sample_begin_ms=2000u,sample_end_ms=3000u;
extern volatile uint32_t motor_pulse_channel;
volatile int32_t motor_speed_values[4],motor_speed_min,motor_speed_max,motor_speed_sum;
volatile uint32_t motor_speed_frames,motor_speed_last_ms,motor_speed_mode,motor_speed_fault,motor_speed_samples;
volatile int32_t motor_speed_count_first,motor_speed_count_last;
volatile uint32_t motor_speed_time_first,motor_speed_time_last;
/* Snapshot at the first fault, before zero-PWM changes live state.
 * Causes: 1 hard driver speed,2 consecutive soft speed,3 count-filtered
 * speed,4 stale feedback,5 UART,6 reverse sign,7 other channel motion. */
volatile uint32_t motor_fault_cause,motor_fault_ms,motor_fault_elapsed,motor_fault_channel,motor_fault_mode;
volatile int32_t motor_fault_driver_speed,motor_fault_filtered_speed,motor_fault_pwm;
volatile uint32_t motor_fault_streak;
static void latch_motor_fault(uint32_t now,uint32_t fault,uint32_t cause)
{
    if(!motor_pulse_active)return;
    motor_speed_fault=fault;motor_fault_cause=cause;motor_fault_ms=now;
    motor_fault_elapsed=now-motor_pulse_started_ms;
    motor_fault_channel=motor_pulse_channel;motor_fault_mode=motor_speed_mode;
    motor_fault_driver_speed=motor_speed_values[motor_pulse_channel-1u];
    motor_fault_filtered_speed=motor_control_speed;motor_fault_pwm=motor_control_pwm;
    motor_fault_streak=overspeed_streak;motor_stop();
}

void motor_stop(void)
{
    motor_pulse_active=0;motor_speed_mode=0;stop_repeats=3;
}

/* Bench-only official channels: M1 left front, M2 left rear, M3 right front, M4 right rear.
 * No arbitrary PWM/speed passthrough. Fresh valid voltage reply is required.
 * Query parser below accepts the measured module format $Battery:8.2V#.
 */
static uint32_t good_voltage_ms;
static uint8_t have_voltage;
static char voltage_line[96];
static unsigned voltage_length;
static uint8_t collecting,upload_pending,upload_boot_disabled;
static uint32_t upload_started_ms;
volatile int32_t motor_encoder_counts[4];
volatile uint32_t motor_encoder_frames,motor_encoder_last_ms,motor_encoder_upload_enabled;
volatile uint8_t motor_parameter_raw[384];
volatile uint32_t motor_parameter_bytes,motor_parameter_capture;
static uint8_t parameter_pending;
static const char *const parameter_commands[]={"$read_flash#","$mtype:3#","$mline:13#","$mphase:45#","$wdiameter:65#"};
static uint32_t parameter_started_ms;
int motor_parameter_write(uint32_t now,unsigned parameter)
{
    if(parameter>4u)return 0;
    if(tx || stop_repeats || motor_pulse_active || upload_pending ||
       motor_encoder_upload_enabled || parameter_pending || motor_parameter_capture)return 0;
    motor_parameter_bytes=0;motor_parameter_capture=1;
    parameter_pending=(uint8_t)(parameter+1u);parameter_started_ms=now;return 1;
}
int motor_parameter_read(uint32_t now)
{
    return motor_parameter_write(now,0);
}

int motor_encoder_upload(uint32_t now,unsigned enable)
{
    if(enable>1u || parameter_pending || motor_parameter_capture || tx || upload_pending || stop_repeats || motor_pulse_active)return 0;
    upload_pending=enable?1u:2u;upload_started_ms=now;
    motor_encoder_upload_enabled=enable;return 1;
}

static void accept_encoder_frame(uint32_t now)
{
    char *p=voltage_line+6,*end;int32_t values[4];unsigned i;
    int speed_frame=!strncmp(voltage_line,"$MSPD:",6);
    if(!speed_frame && strncmp(voltage_line,"$MAll:",6))return;
    for(i=0;i<4u;i++){
        long value;
        if(!((*p>='0' && *p<='9') || (*p=='-' && p[1]>='0' && p[1]<='9')))return;
        errno=0;
        if(speed_frame){
            double v=strtod(p,&end);
            if(!isfinite(v) || v>2000.0 || v<-2000.0)return;
            value=(long)v;
        }else value=strtol(p,&end,10);
        if(errno==ERANGE || end==p || *end!=(i==3u?'#':','))return;
        values[i]=(int32_t)value;p=end+1;
    }
    if(*p)return;
    if(speed_frame){
        for(i=0;i<4u;i++)motor_speed_values[i]=values[i];
        ++motor_speed_frames;motor_speed_last_ms=now;
        /* Suspended low-speed trial: reject hard spikes immediately and
         * sustained soft-limit violations using fresh consecutive frames.
         * Stale data and other fault guards below remain active. */
        if(motor_pulse_active && motor_speed_mode==3u &&
           (uint32_t)(now-motor_pulse_started_ms)>700u){
            int32_t v=values[motor_pulse_channel-1u];
            if(v>800 || v<-800)latch_motor_fault(now,3,1);
            else if(v>320 || v<-320){
                if(++overspeed_streak>=3u)latch_motor_fault(now,3,2);
            }else overspeed_streak=0;
        }

        if(motor_speed_mode && motor_pulse_active &&
           (uint32_t)(now-motor_pulse_started_ms)>=sample_begin_ms &&
           (uint32_t)(now-motor_pulse_started_ms)<=sample_end_ms){
            int32_t value=values[motor_pulse_channel-1u];
            if(!motor_speed_samples){motor_speed_count_first=motor_encoder_counts[motor_pulse_channel-1u];motor_speed_time_first=now;}
            motor_speed_count_last=motor_encoder_counts[motor_pulse_channel-1u];motor_speed_time_last=now;
            if(!motor_speed_samples || value<motor_speed_min)motor_speed_min=value;
            if(!motor_speed_samples || value>motor_speed_max)motor_speed_max=value;
            motor_speed_sum+=value;++motor_speed_samples;
        }
        return;
    }
    for(i=0;i<4u;i++)motor_encoder_counts[i]=values[i];
    ++motor_encoder_frames;motor_encoder_last_ms=now;
}


volatile uint32_t motor_pulse_channel;
static const char *const pulses[4]={"$pwm:900,0,0,0#","$pwm:0,900,0,0#","$pwm:0,0,900,0#","$pwm:0,0,0,900#"};

int motor_pulse_start(uint32_t now,unsigned channel)
{
    if(parameter_pending || motor_parameter_capture || channel<1u || channel>4u || motor_pulse_active || stop_repeats || tx || !have_voltage ||
       (uint32_t)(now-good_voltage_ms)>1500u ||
       (motor_pulse_count && (uint32_t)(now-motor_pulse_stopped_ms)<3000u))return 0;
    if(motor_encoder_upload_enabled && (!motor_encoder_frames ||
       (uint32_t)(now-motor_encoder_last_ms)>500u || motor_rx_errors || motor_rx_drops))return 0;
    motion_deadline_ms=250u;motor_speed_mode=0;motor_speed_fault=0;overspeed_streak=0;
    motor_fault_cause=0;motor_fault_ms=0;motor_fault_elapsed=0;motor_fault_channel=0;motor_fault_mode=0;
    motor_fault_driver_speed=0;motor_fault_filtered_speed=0;motor_fault_pwm=0;motor_fault_streak=0;
    tx=pulses[channel-1u];motor_pulse_channel=channel;motor_pulse_active=1;
    motor_pulse_started_ms=now;++motor_pulse_count;return 1;
}

static const char *const speed_commands[]={"$spd:80,0,0,0#","$spd:0,80,0,0#","$spd:0,0,80,0#","$spd:0,0,0,80#"};
int motor_speed_start(uint32_t now,unsigned channel)
{
    if(!motor_encoder_upload_enabled || !motor_speed_frames || !motor_encoder_frames ||
       (uint32_t)(now-motor_speed_last_ms)>250u || (uint32_t)(now-motor_encoder_last_ms)>250u ||
       motor_rx_errors || motor_rx_drops)return 0;
    if(!motor_pulse_start(now,channel))return 0;
    tx=speed_commands[channel-1u];motion_deadline_ms=3200u;motor_speed_mode=1;sample_begin_ms=2000u;sample_end_ms=3000u;
    motor_speed_samples=0;motor_speed_sum=0;motor_speed_min=0;motor_speed_max=0;
    motor_speed_count_first=0;motor_speed_count_last=0;motor_speed_time_first=0;motor_speed_time_last=0;
    return 1;
}

static char calibration_command[40];
static uint8_t hold_pending;
static char hold_command[40];
int motor_calibration_start(uint32_t now,unsigned channel,unsigned level)
{
    static const unsigned pwm_levels[]={25u,300u,700u,500u,600u,400u,350u,450u,375u};
    unsigned values[4]={0,0,0,0};
    if(channel<1u || channel>4u || level<1u || level>9u)return 0;
    if(!motor_speed_start(now,channel))return 0;
    values[channel-1u]=pwm_levels[level-1u];
    snprintf(calibration_command,sizeof(calibration_command),"$pwm:%u,%u,%u,%u#",values[0],values[1],values[2],values[3]);
    tx=calibration_command;motion_deadline_ms=2200u;motor_speed_mode=2;
    sample_begin_ms=800u;sample_end_ms=1800u;return 1;
}

/* Separate static breakaway from holding drive: fixed suspended profiles.
 * Kick350PWM250ms, then one fixed holding output; never autonomous on boot. */
int motor_startup_hold_start(uint32_t now,unsigned channel,unsigned level)
{
    static const unsigned holds[]={150u,200u,250u,300u};
    unsigned v[4]={0,0,0,0};
    if(channel<1u || channel>4u || level<1u || level>4u || !motor_speed_start(now,channel))return 0;
    v[channel-1u]=holds[level-1u];
    snprintf(hold_command,sizeof(hold_command),"$pwm:%u,%u,%u,%u#",v[0],v[1],v[2],v[3]);
    v[channel-1u]=350u;
    snprintf(calibration_command,sizeof(calibration_command),"$pwm:%u,%u,%u,%u#",v[0],v[1],v[2],v[3]);
    tx=calibration_command;motor_speed_mode=4;hold_pending=1;motor_control_pwm=350;
    motor_control_speed=0;motion_deadline_ms=2200u;sample_begin_ms=800u;sample_end_ms=1800u;
    return 1;
}

static void startup_hold_poll(uint32_t now)
{
    if(!motor_pulse_active || motor_speed_mode!=4u){hold_pending=0;return;}
    if(hold_pending && !tx && (uint32_t)(now-motor_pulse_started_ms)>=250u){
        tx=hold_command;hold_pending=0;
        /* Parse our internally generated channel value only, not external input. */
        unsigned values[4];
        if(sscanf(hold_command,"$pwm:%u,%u,%u,%u#",&values[0],&values[1],&values[2],&values[3])==4)
            motor_control_pwm=(int32_t)values[motor_pulse_channel-1u];
    }
}

int motor_closed_start(uint32_t now,unsigned channel)
{
    unsigned values[4]={0,0,0,0};
    if(channel<1u || channel>4u || !motor_speed_start(now,channel))return 0;
    values[channel-1u]=350u;
    snprintf(control_command,sizeof(control_command),"$pwm:%u,%u,%u,%u#",values[0],values[1],values[2],values[3]);
    tx=control_command;motor_speed_mode=3;motion_deadline_ms=12000u;
    sample_begin_ms=8000u;sample_end_ms=11000u;
    motor_control_pwm=350;closed_kick_pending=1;motor_control_speed=0;motor_control_updates=0;
    control_last_ms=now;control_prev_count=motor_encoder_counts[channel-1u];
    control_integral_q8=0;control_filtered_q8=0;return 1;
}

static void control_poll(uint32_t now)
{
    uint32_t dt=now-control_last_ms;int32_t count,delta,raw_q8,error_q8,output;
    unsigned values[4]={0,0,0,0};
    if(!motor_pulse_active || motor_speed_mode!=3u || dt<250u || tx)return;
    count=motor_encoder_counts[motor_pulse_channel-1u];delta=count-control_prev_count;
    control_prev_count=count;control_last_ms=now;
    /* 65mm nominal wheel,2340counts/revolution; signed integer arithmetic. */
    raw_q8=(int32_t)((int64_t)delta*204203*256/(2340u*dt));
    control_filtered_q8=(control_filtered_q8+raw_q8)/2;
    motor_control_speed=control_filtered_q8/256;
    error_q8=120*256-control_filtered_q8;
    if(closed_kick_pending){
        /* First control window ends the kick. Select independently measured
         * holding output before ordinary gradual correction. */
        closed_kick_pending=0;control_integral_q8=0;
        output=control_feedforward[motor_pulse_channel-1u];
    }else{
        /* Slow correction retains bounded increments and feedback guards. */
        output=0;
        if(error_q8>5*256 || error_q8<-5*256)control_integral_q8+=error_q8/40;
        else control_integral_q8=0;
        output=control_integral_q8/256;control_integral_q8-=output*256;
        if(output>5)output=5;
        if(output<-5)output=-5;
        output+=motor_control_pwm;
    }
    if(output<0)output=0;
    if(output>700)output=700;
    motor_control_pwm=output;++motor_control_updates;
    values[motor_pulse_channel-1u]=(unsigned)output;
    snprintf(control_command,sizeof(control_command),"$pwm:%u,%u,%u,%u#",values[0],values[1],values[2],values[3]);
    tx=control_command;
}

void USART3_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
void USART3_IRQHandler(void)
{
    uint32_t status=USART3->STATR;
    if(status&(USART_FLAG_RXNE|USART_FLAG_ORE|USART_FLAG_FE|USART_FLAG_NE|USART_FLAG_PE)){
        uint8_t byte=(uint8_t)USART3->DATAR;
        uint32_t next=(rx_head+1u)&2047u;
        if(status&(USART_FLAG_ORE|USART_FLAG_FE|USART_FLAG_NE|USART_FLAG_PE))++motor_rx_errors;
        else{
            ++motor_rx_bytes;
            if(next==rx_tail)++motor_rx_drops;
            else{rx[rx_head]=byte;rx_head=next;}
        }
    }
    if(USART_GetITStatus(USART3,USART_IT_TXE)!=RESET){
        if(tx){
            USART_SendData(USART3,(uint8_t)*tx++);++motor_tx_bytes;
            if(!*tx){
                tx=0;USART_ITConfig(USART3,USART_IT_TXE,DISABLE);
                if(stop_frame){stop_frame=0;++motor_pulse_stops;motor_pulse_stopped_ms=tick_ms;}
            }
        }else USART_ITConfig(USART3,USART_IT_TXE,DISABLE);
    }
}

void motor_probe_init(void)
{
    GPIO_InitTypeDef gpio={0};USART_InitTypeDef uart={0};NVIC_InitTypeDef irq={0};
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_AFIO|RCC_APB2Periph_GPIOD,ENABLE);
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_USART3,ENABLE);
    GPIO_PinRemapConfig(GPIO_FullRemap_USART3,ENABLE);
    GPIO_SetBits(GPIOD,GPIO_Pin_8);
    gpio.GPIO_Pin=GPIO_Pin_8;gpio.GPIO_Mode=GPIO_Mode_AF_PP;gpio.GPIO_Speed=GPIO_Speed_10MHz;
    GPIO_Init(GPIOD,&gpio);
    gpio.GPIO_Pin=GPIO_Pin_9;gpio.GPIO_Mode=GPIO_Mode_IPU;GPIO_Init(GPIOD,&gpio);
    USART_StructInit(&uart);uart.USART_BaudRate=115200;
    uart.USART_Mode=USART_Mode_Rx|USART_Mode_Tx;USART_Init(USART3,&uart);
    irq.NVIC_IRQChannel=USART3_IRQn;irq.NVIC_IRQChannelPreemptionPriority=2;
    irq.NVIC_IRQChannelSubPriority=0;irq.NVIC_IRQChannelCmd=ENABLE;NVIC_Init(&irq);
    USART_ITConfig(USART3,USART_IT_RXNE,ENABLE);USART_Cmd(USART3,ENABLE);
}

void motor_probe_poll(uint32_t now)
{
    unsigned budget=256;
    while(rx_tail!=rx_head && budget--){
        uint8_t byte=rx[rx_tail];
        if(motor_parameter_capture && motor_parameter_bytes<sizeof(motor_parameter_raw))
            motor_parameter_raw[motor_parameter_bytes++]=byte;
        motor_log[motor_log_count&127u]=byte;
        rx_tail=(rx_tail+1u)&2047u;++motor_log_count;motor_last_rx_ms=now;
        if(byte=='$'){voltage_length=0;collecting=1;}
        if(!collecting)continue;
        if(voltage_length>=sizeof(voltage_line)-1u){collecting=0;voltage_length=0;continue;}
        voltage_line[voltage_length++]=(char)byte;
        if(byte=='#'){
            unsigned whole,decimal;char ending;
            voltage_line[voltage_length]=0;
            if(sscanf(voltage_line,"$Battery:%u.%uV%c",&whole,&decimal,&ending)==3 && ending=='#' &&
               ((whole>=6u && whole<=7u) || (whole==8u && decimal<=5u))){
                good_voltage_ms=now;have_voltage=1;
            }
            accept_encoder_frame(now);
            voltage_length=0;collecting=0;
        }
    }
    if(motor_pulse_active && motor_speed_mode){
        unsigned i;uint32_t fault=0,cause=0,elapsed=(uint32_t)(now-motor_pulse_started_ms);
        if((uint32_t)(now-motor_speed_last_ms)>250u || (uint32_t)(now-motor_encoder_last_ms)>250u){fault=1;cause=4;}
        else if(motor_rx_errors || motor_rx_drops){fault=2;cause=5;}
        else if(elapsed>(motor_speed_mode==3u?700u:300u)){
            int32_t speed=motor_speed_values[motor_pulse_channel-1u];
            if(motor_speed_mode==3u){
                if(motor_control_speed>320 || motor_control_speed<-320){fault=3;cause=3;}
            }else if(speed>(motor_speed_mode==2u?800:320) || speed<-(motor_speed_mode==2u?800:320)){fault=3;cause=1;}
            if(!fault && speed<-30){fault=4;cause=6;}
            for(i=0;i<4u;i++)if(i!=motor_pulse_channel-1u &&
                (motor_speed_values[i]>50 || motor_speed_values[i]<-50)){fault=5;cause=7;}
        }
        if(fault)latch_motor_fault(now,fault,cause);
    }
    if(motor_pulse_active && (uint32_t)(now-motor_pulse_started_ms)>=motion_deadline_ms){
        /* Complete any partial query/drive frame before sending stop frames. */
        motor_pulse_active=0;motor_speed_mode=0;stop_repeats=3;motor_pulse_stopped_ms=now;
    }
    if(motor_encoder_upload_enabled && (uint32_t)(now-upload_started_ms)>=60000u){
        motor_encoder_upload_enabled=0;upload_pending=2u;
    }
    if(motor_parameter_capture && (uint32_t)(now-parameter_started_ms)>=3000u)
        motor_parameter_capture=0;
    startup_hold_poll(now);
    control_poll(now);
    if(!tx){
        if(stop_repeats){tx="$pwm:0,0,0,0#";--stop_repeats;stop_frame=1;}
        else if(!zero_sent){tx="$pwm:0,0,0,0#";zero_sent=1;last_query_ms=now;}
        else if(!upload_boot_disabled){tx="$upload:0,0,0#";upload_boot_disabled=1;}
        else if(parameter_pending){tx=parameter_commands[parameter_pending-1u];parameter_pending=0;}
        else if(upload_pending){tx=upload_pending==1u?"$upload:1,0,1#":"$upload:0,0,0#";upload_pending=0;}
        else if(!motor_pulse_active && (uint32_t)(now-last_query_ms)>=(query_started?1000u:500u)){
            tx="$read_vol#";last_query_ms=now;query_started=1;++motor_queries;
        }
    }
    if(tx)USART_ITConfig(USART3,USART_IT_TXE,ENABLE);
}
