#include "uvc_bridge.h"
#include "motor_probe.h"
#include "ultrasonic.h"
#include "servo_probe.h"
#include "motor_telemetry.h"
#include "debug.h"
#include "vision_uart.h"
#include "oled_probe.h"
#include "oled_display.h"
#include "oled_probe2.h"
#include "oled_display2.h"
#include "oled_probe3.h"
#include "oled_display3.h"
#include "vision_labels.h"
#include <stdio.h>
#include "encoder_decode.h"
#include "storage_probe.h"
#include "settings.h"
extern volatile encoder_decode_t encoder_state;
extern volatile uint32_t warning_mm,warning_change_ms,warning_ui_active,save_key_requests;
extern volatile uint32_t trend_valid,trend_kind,trend_samples;
extern volatile int32_t trend_closing_mm_s;
extern volatile uint32_t buzzer_muted,mute_key_presses,mute_key_level,buzzer_is_on,led_is_on;
#include <string.h>

/* Vision messages only update vision state; explicit MOTOR_* bench commands
 * request bounded motor diagnostics through motor_probe.
 * R1 J2: RX1(PA10) <-> TX_0; TX1(PA9) <-> RX_0. 115200 8N1. */
volatile uint32_t phone_monitor_valid,phone_monitor_state,phone_monitor_last_ms;
volatile uint32_t vision_link_valid;
volatile uint32_t vision_valid, vision_seq, vision_class=255;
volatile uint32_t vision_score, vision_cx, vision_cy, vision_last_ms;
volatile uint32_t vision_accepted, vision_rejected, vision_rx_errors;
extern volatile uint32_t range_rounds, range_status, range_corrected_mm;
extern volatile int32_t range_init_error,range_error,range_loaded_offset_um;
extern volatile uint32_t range_needs_reinit,range_reinit_attempts,range_reinit_successes;
extern volatile uint32_t guard_state,red_is_on,green_is_on;

static volatile uint8_t rx[256];
static volatile uint32_t rx_head, rx_tail;
static uint8_t tx[256];
static uint32_t tx_head, tx_tail, seen_errors;
static char line[96];
static unsigned line_length;
static uint8_t discarding, have_sequence;

void USART1_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
void USART1_IRQHandler(void)
{
    uint32_t status=USART1->STATR;
    if(status & (USART_FLAG_RXNE|USART_FLAG_ORE|USART_FLAG_FE|USART_FLAG_NE|USART_FLAG_PE)){
        uint8_t byte=(uint8_t)USART1->DATAR; /* STATR then DATAR clears errors. */
        uint32_t next=(rx_head+1u)&255u;
        if(status & (USART_FLAG_ORE|USART_FLAG_FE|USART_FLAG_NE|USART_FLAG_PE)){
            ++vision_rx_errors;
        }else if(next==rx_tail){
            ++vision_rx_errors;
        }else{
            rx[rx_head]=byte;
            rx_head=next;
        }
    }
}

void vision_uart_init(void)
{
    GPIO_InitTypeDef gpio={0};
    USART_InitTypeDef uart={0};
    NVIC_InitTypeDef irq={0};
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA|RCC_APB2Periph_USART1,ENABLE);
    GPIO_SetBits(GPIOA,GPIO_Pin_9);
    gpio.GPIO_Pin=GPIO_Pin_9;gpio.GPIO_Mode=GPIO_Mode_AF_PP;gpio.GPIO_Speed=GPIO_Speed_10MHz;
    GPIO_Init(GPIOA,&gpio);
    gpio.GPIO_Pin=GPIO_Pin_10;gpio.GPIO_Mode=GPIO_Mode_IPU;
    GPIO_Init(GPIOA,&gpio);
    USART_StructInit(&uart);
    uart.USART_BaudRate=115200;
    uart.USART_Mode=USART_Mode_Rx|USART_Mode_Tx;
    USART_Init(USART1,&uart);
    irq.NVIC_IRQChannel=USART1_IRQn;
    irq.NVIC_IRQChannelPreemptionPriority=1; /* Warning timer stays priority 0. */
    irq.NVIC_IRQChannelSubPriority=0;irq.NVIC_IRQChannelCmd=ENABLE;
    NVIC_Init(&irq);
    USART_ITConfig(USART1,USART_IT_RXNE,ENABLE);
    USART_Cmd(USART1,ENABLE);
}

static void (*usb_reply_sink)(const char *);
static void reply(const char *message)
{
    if(usb_reply_sink){usb_reply_sink(message);return;}
    unsigned i, n=(unsigned)strlen(message);
    if(n>255u-((tx_head-tx_tail)&255u))return;
    for(i=0;i<n;i++){tx[tx_head]=(uint8_t)message[i];tx_head=(tx_head+1u)&255u;}
}
static uint8_t checksum(const char *s, unsigned n)
{
    unsigned i,b;uint8_t c=0;
    for(i=0;i<n;i++){
        c^=(uint8_t)s[i];
        for(b=0;b<8;b++)c=(uint8_t)((c<<1)^((c&128u)?7u:0u));
    }
    return c;
}
static int hex_digit(char c)
{
    if(c>='0' && c<='9')return c-'0';
    if(c>='A' && c<='F')return c-'A'+10;
    return -1;
}
static int decimal(const char **cursor,uint32_t *out,char terminator)
{
    const char *p=*cursor;uint32_t value=0;unsigned count=0;
    while(*p>='0' && *p<='9'){
        unsigned digit=(unsigned)(*p++-'0');
        if(value>(0xFFFFFFFFu-digit)/10u || ++count>10)return 0;
        value=value*10u+digit;
    }
    if(!count || *p!=terminator)return 0;
    *cursor=p+(terminator!=0);*out=value;return 1;
}
static void accept_line(char *line,uint32_t now)
{
    char *star;const char *p;char response[160];int hi,lo;
    uint32_t seq,cls,score,cx,cy;
    if(uvc_bridge_command(line,now,reply))return;
    if(!strcmp(line,"HELLO")){
        have_sequence=0;phone_monitor_valid=0;vision_link_valid=0;vision_valid=0;vision_class=255;
        reply("ZXR,V1\n");return;
    }
    if(!strcmp(line,"PING")){reply("PONG\n");return;}



    if(!strcmp(line,"GIMBAL_MANUAL_START")){
        reply(servo_probe_manual_start(now)?"GIMBAL_MANUAL_STARTED\n":"GIMBAL_BUSY\n");return;
    }
    if(!strncmp(line,"GIMBAL_SET,",11)){
        uint32_t yaw,pitch;p=line+11;
        if(!decimal(&p,&yaw,',') || !decimal(&p,&pitch,0) ||
           !servo_probe_manual_set(now,yaw,pitch)){reply("GIMBAL_SET_REJECTED\n");return;}
        reply("GIMBAL_SET_ACCEPTED\n");return;
    }
    if(!strcmp(line,"GIMBAL_RUN")){
        reply(servo_probe_run(now)?"GIMBAL_RUN_STARTED\n":"GIMBAL_BUSY\n");return;
    }
    if(!strcmp(line,"GIMBAL_KEEPALIVE")){
        reply(servo_probe_keepalive(now)?"GIMBAL_ALIVE\n":"GIMBAL_NOT_RUNNING\n");return;
    }
    if(!strcmp(line,"GIMBAL_RANDOM_STATUS")){
        gimbal_snapshot_t g;servo_probe_snapshot(&g);
        snprintf(response,sizeof(response),"RANDOM,%lu,%lu,%lu,%lu,%lu\n",
            (unsigned long)g.target_yaw,(unsigned long)g.target_pitch,
            (unsigned long)g.targets,(unsigned long)g.lease_age_ms,
            (unsigned long)g.lease_stops);reply(response);return;
    }
    if(!strcmp(line,"GIMBAL_STATUS")){
        gimbal_snapshot_t g;servo_probe_snapshot(&g);
        snprintf(response,sizeof(response),"GIMBAL,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu\n",
            (unsigned long)now,(unsigned long)g.ready,(unsigned long)g.active,
            (unsigned long)g.mode,(unsigned long)g.yaw_us,(unsigned long)g.pitch_us,
            (unsigned long)g.starts,(unsigned long)g.stops,
            (unsigned long)g.yaw_hz,(unsigned long)g.pitch_hz);reply(response);return;
    }
    if(!strcmp(line,"GIMBAL_YAW") || !strcmp(line,"GIMBAL_PITCH") || !strcmp(line,"GIMBAL_BOTH")){
        unsigned mode=!strcmp(line,"GIMBAL_YAW")?1u:(!strcmp(line,"GIMBAL_PITCH")?2u:3u);
        reply(servo_probe_start(now,mode)?"GIMBAL_STARTED\n":"GIMBAL_BUSY\n");return;
    }
    if(!strcmp(line,"GIMBAL_STOP")){servo_probe_stop();reply("GIMBAL_STOPPED\n");return;}
    if(!strcmp(line,"ULTRA_STATUS")){
        ultra_state_t u;ultrasonic_snapshot(&u);
        snprintf(response,sizeof(response),"ULTRA,%lu,%u,%u,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu\n",
            (unsigned long)now,(unsigned)u.valid,(unsigned)u.status,
            (unsigned long)u.distance_mm,(unsigned long)u.pulse_us,
            (unsigned long)u.trigger_count,(unsigned long)u.good_count,
            (unsigned long)u.timeout_count,(unsigned long)u.edge_count,
            (unsigned long)u.reject_count,(unsigned long)(now-u.last_good_ms),
            (unsigned long)ultrasonic_timer_hz);reply(response);return;
    }
    /* Sensor bench firmware: only STOP accepted from motor command family. */
    if(!strncmp(line,"MOTOR_",6) && strcmp(line,"MOTOR_STOP") && strcmp(line,"MOTOR_DASH_STATUS") && strcmp(line,"MOTOR_STATUS")){
        reply("MOTOR_DISABLED_SENSOR_TEST\n");return;
    }

    if(!strcmp(line,"MOTOR_MONITOR_ON") || !strcmp(line,"MOTOR_MONITOR_OFF")){
        unsigned enable=!strcmp(line,"MOTOR_MONITOR_ON");
        reply(motor_monitor(now,enable)?"MONITOR_QUEUED\n":"MONITOR_BUSY\n");return;
    }
    if(!strcmp(line,"MOTOR_DASH_STATUS")){
        int32_t speeds[4];unsigned i,state;
        int vf=motor_value_fresh(now,motor_voltage_last_ms,motor_voltage_frames,3000u);
        int sf=motor_encoder_upload_enabled && motor_value_fresh(now,motor_speed_last_ms,motor_speed_frames,500u);
        for(i=0;i<4;i++)speeds[i]=motor_speed_values[i];
        state=motor_dashboard_state(sf,speeds,motor_pulse_active,motor_fault_cause,
            motor_rx_errors,motor_rx_drops,vf,motor_voltage_mv);
        snprintf(response,sizeof(response),"MOTORDASH,%lu,%lu,%u,%lu,%u,%ld,%ld,%ld,%ld,%lu,%u,%lu,%lu,%lu\n",
            (unsigned long)now,(unsigned long)motor_voltage_mv,vf,
            (unsigned long)(now-motor_voltage_last_ms),sf,
            (long)speeds[0],(long)speeds[1],(long)speeds[2],(long)speeds[3],
            (unsigned long)motor_pulse_active,state,(unsigned long)motor_fault_cause,
            (unsigned long)motor_monitor_enabled,(unsigned long)motor_encoder_upload_enabled);
        reply(response);return;
    }

    if(!strncmp(line,"MOTOR_START_M",13) && line[13]>='1' && line[13]<='4' &&
       line[14]=='_' && line[15]>='1' && line[15]<='4' && !line[16]){
        unsigned channel=(unsigned)(line[13]-'0'),level=(unsigned)(line[15]-'0');
        if(motor_startup_hold_start(now,channel,level)){
            snprintf(response,sizeof(response),"MOTOR_START_STARTED,M%u,L%u\n",channel,level);reply(response);
        }else reply("MOTOR_START_BUSY_OR_OFFLINE\n");return;
    }
    if(!strncmp(line,"MOTOR_CLOSED_M",14) && line[14]>='1' && line[14]<='4' && !line[15]){
        unsigned channel=(unsigned)(line[14]-'0');
        if(motor_closed_start(now,channel)){
            snprintf(response,sizeof(response),"MOTOR_CLOSED_STARTED,M%u\n",channel);reply(response);
        }else reply("MOTOR_CLOSED_BUSY_OR_OFFLINE\n");return;
    }
    if(!strcmp(line,"MOTOR_FAULT_STATUS")){
        snprintf(response,sizeof(response),"MOTORFAULT,%lu,%lu,%lu,%lu,%lu,%ld,%ld,%ld,%lu\n",
            (unsigned long)motor_fault_cause,(unsigned long)motor_fault_ms,
            (unsigned long)motor_fault_elapsed,(unsigned long)motor_fault_channel,
            (unsigned long)motor_fault_mode,(long)motor_fault_driver_speed,
            (long)motor_fault_filtered_speed,(long)motor_fault_pwm,
            (unsigned long)motor_fault_streak);reply(response);return;
    }
    if(!strcmp(line,"MOTOR_LIVE_STATUS")){
        snprintf(response,sizeof(response),"MOTORLIVE,%lu,%lu,%lu,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%lu,%lu,%lu,%lu\n",
            (unsigned long)now,(unsigned long)(now-motor_encoder_last_ms),
            (unsigned long)(now-motor_speed_last_ms),
            (long)motor_encoder_counts[0],(long)motor_encoder_counts[1],
            (long)motor_encoder_counts[2],(long)motor_encoder_counts[3],
            (long)motor_speed_values[0],(long)motor_speed_values[1],
            (long)motor_speed_values[2],(long)motor_speed_values[3],
            (long)motor_control_speed,(long)motor_control_pwm,
            (unsigned long)motor_pulse_active,(unsigned long)motor_pulse_channel,
            (unsigned long)motor_speed_mode,(unsigned long)motor_speed_fault);
        reply(response);return;
    }
    if(!strcmp(line,"MOTOR_CONTROL_STATUS")){
        snprintf(response,sizeof(response),"CONTROL,%ld,%ld,%lu\n",
            (long)motor_control_speed,(long)motor_control_pwm,(unsigned long)motor_control_updates);
        reply(response);return;
    }
    if(!strncmp(line,"MOTOR_CAL_M",11) && line[11]>='1' && line[11]<='4' &&
        line[12]=='_' && line[13]>='1' && line[13]<='9' && !line[14]){
        unsigned channel=(unsigned)(line[11]-'0'),level=(unsigned)(line[13]-'0');
        if(motor_calibration_start(now,channel,level)){
            snprintf(response,sizeof(response),"MOTOR_CAL_STARTED,M%u,L%u\n",channel,level);reply(response);
        }else reply("MOTOR_CAL_BUSY_OR_OFFLINE\n");return;
    }
    if(!strcmp(line,"MOTOR_STOP")){motor_stop();reply("MOTOR_STOP_QUEUED\n");return;}
    if(!strncmp(line,"MOTOR_SPEED_M",13) && line[13]>='1' && line[13]<='4' && !line[14]){
        unsigned channel=(unsigned)(line[13]-'0');
        if(motor_speed_start(now,channel)){
            snprintf(response,sizeof(response),"MOTOR_SPEED_STARTED,M%u\n",channel);reply(response);
        }else reply("MOTOR_SPEED_BUSY_OR_OFFLINE\n");return;
    }
    if(!strcmp(line,"MOTOR_SPEED_WINDOW")){
        snprintf(response,sizeof(response),"SPEEDWINDOW,%ld,%ld,%lu,%lu\n",
            (long)motor_speed_count_first,(long)motor_speed_count_last,
            (unsigned long)motor_speed_time_first,(unsigned long)motor_speed_time_last);
        reply(response);return;
    }
    if(!strcmp(line,"MOTOR_SPEED_STATUS")){
        snprintf(response,sizeof(response),"SPEED,%lu,%lu,%ld,%ld,%ld,%ld,%lu,%lu,%lu,%ld,%ld,%ld\n",
            (unsigned long)motor_speed_frames,(unsigned long)(now-motor_speed_last_ms),
            (long)motor_speed_values[0],(long)motor_speed_values[1],(long)motor_speed_values[2],(long)motor_speed_values[3],
            (unsigned long)motor_speed_mode,(unsigned long)motor_speed_fault,(unsigned long)motor_speed_samples,
            (long)motor_speed_sum,(long)motor_speed_min,(long)motor_speed_max);
        reply(response);return;
    }
    if(!strncmp(line,"MOTOR_CONFIG_",13) && line[13]>='1' && line[13]<='4' && !line[14]){
        unsigned parameter=(unsigned)(line[13]-'0');
        reply(motor_parameter_write(now,parameter)?"PARAM_WRITE_QUEUED\n":"PARAM_WRITE_BUSY\n");return;
    }
    if(!strcmp(line,"MOTOR_PARAM_READ")){
        reply(motor_parameter_read(now)?"PARAM_READ_QUEUED\n":"PARAM_READ_BUSY\n");return;
    }
    if(!strcmp(line,"MOTOR_PARAM_STATUS")){
        snprintf(response,sizeof(response),"PARAM,%lu,%lu\n",
            (unsigned long)motor_parameter_bytes,(unsigned long)motor_parameter_capture);
        reply(response);return;
    }
    if(!strncmp(line,"MOTOR_PARAM_DATA_",17) && line[17]>='0' && line[17]<='5' && !line[18]){
        unsigned offset=(unsigned)(line[17]-'0')*64u,i,at;
        at=(unsigned)snprintf(response,sizeof(response),"PARAMDATA,");
        for(i=offset;i<offset+64u && i<motor_parameter_bytes;i++)
            at+=(unsigned)snprintf(response+at,sizeof(response)-at,"%02X",motor_parameter_raw[i]);
        response[at++]='\n';response[at]=0;reply(response);return;
    }
    if(!strcmp(line,"MOTOR_ENCODER_ON") || !strcmp(line,"MOTOR_ENCODER_OFF")){
        unsigned enable=!strcmp(line,"MOTOR_ENCODER_ON");
        reply(motor_encoder_upload(now,enable)?"ENCODER_UPLOAD_QUEUED\n":"ENCODER_UPLOAD_BUSY\n");return;
    }
    if(!strcmp(line,"MOTOR_ENCODER_STATUS")){
        snprintf(response,sizeof(response),"ENCODER,%lu,%lu,%ld,%ld,%ld,%ld,%lu\n",
            (unsigned long)motor_encoder_frames,(unsigned long)(now-motor_encoder_last_ms),
            (long)motor_encoder_counts[0],(long)motor_encoder_counts[1],
            (long)motor_encoder_counts[2],(long)motor_encoder_counts[3],
            (unsigned long)motor_encoder_upload_enabled);
        reply(response);return;
    }
    if(!strncmp(line,"MOTOR_TEST_M",12) && line[12]>='1' && line[12]<='4' && !line[13]){
        unsigned channel=(unsigned)(line[12]-'0');
        if(motor_pulse_start(now,channel)){
            snprintf(response,sizeof(response),"MOTOR_TEST_STARTED,M%u\n",channel);reply(response);
        }else reply("MOTOR_TEST_BUSY_OR_OFFLINE\n");
        return;
    }
    if(!strcmp(line,"MOTOR_PULSE_STATUS")){
        snprintf(response,sizeof(response),"PULSE,%lu,%lu,%lu,%lu,%lu,%lu\n",
            (unsigned long)motor_pulse_active,(unsigned long)motor_pulse_count,
            (unsigned long)motor_pulse_stops,(unsigned long)motor_pulse_started_ms,
            (unsigned long)motor_pulse_stopped_ms,(unsigned long)motor_pulse_channel);
        reply(response);return;
    }
    if(!strcmp(line,"MOTOR_STATUS")){
        snprintf(response,sizeof(response),"MOTOR,%lu,%lu,%lu,%lu,%lu,%lu,%lu\n",
            (unsigned long)motor_rx_bytes,(unsigned long)motor_rx_errors,
            (unsigned long)motor_rx_drops,(unsigned long)motor_queries,
            (unsigned long)motor_tx_bytes,(unsigned long)motor_log_count,
            (unsigned long)(now-motor_last_rx_ms));
        reply(response);return;
    }
    if(!strcmp(line,"MOTOR_RAW")){
        uint32_t count=motor_log_count,n=count<48u?count:48u,i;
        unsigned at=(unsigned)snprintf(response,sizeof(response),"MOTORRAW,");
        for(i=0;i<n;i++)at+=(unsigned)snprintf(response+at,sizeof(response)-at,"%02X",motor_log[(count-n+i)&127u]);
        response[at++]='\n';response[at]=0;reply(response);return;
    }

    if(!strcmp(line,"SETTINGS_STATUS")){
        snprintf(response,sizeof(response),"SETTINGS,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu\n",
            (unsigned long)settings_ready,(unsigned long)settings_busy,(unsigned long)settings_saved_mm,
            (unsigned long)settings_sequence,(unsigned long)settings_loaded,(unsigned long)settings_saves,
            (unsigned long)settings_error,(unsigned long)settings_ui_status,
            (unsigned long)settings_ui_active,(unsigned long)save_key_requests,(unsigned long)settings_saved_muted);
        reply(response);return;
    }
    if(!strncmp(line,"SETTINGS_READ,",14)){
        uint32_t at;uint8_t bytes[32];unsigned i,n;
        p=line+14;
        if(!decimal(&p,&at,0) || !settings_debug_read(at,bytes)){reply("ERR\n");return;}
        n=(unsigned)snprintf(response,sizeof(response),"MEM,%lu,",(unsigned long)at);
        for(i=0;i<32;i++)n+=(unsigned)snprintf(response+n,sizeof(response)-n,"%02X",bytes[i]);
        response[n++]='\n';response[n]=0;reply(response);return;
    }
    if(!strcmp(line,"STORAGE_STATUS")){
        if(!settings_busy)storage_probe_sample();
        snprintf(response,sizeof(response),"STORAGE,%lu,%lu,%lu,%lu,%lu,%lu\n",
            (unsigned long)storage_jedec_id,(unsigned long)storage_sr1,
            (unsigned long)storage_sr2,(unsigned long)storage_probes,
            (unsigned long)storage_matches,(unsigned long)storage_ready);
        reply(response);return;
    }
    if(!strcmp(line,"MUTE_STATUS")){
        snprintf(response,sizeof(response),"MUTE,%lu,%lu,%lu,%lu,%lu\n",
            (unsigned long)buzzer_muted,(unsigned long)mute_key_presses,
            (unsigned long)mute_key_level,(unsigned long)buzzer_is_on,(unsigned long)led_is_on);
        reply(response);return;
    }
    if(!strcmp(line,"TREND_STATUS")){
        snprintf(response,sizeof(response),"TREND,%lu,%lu,%ld,%lu\n",
            (unsigned long)trend_valid,(unsigned long)trend_kind,
            (long)trend_closing_mm_s,(unsigned long)trend_samples);
        reply(response);return;
    }
    if(!strcmp(line,"PARAM_STATUS")){
        snprintf(response,sizeof(response),"PARAM,%lu,%lu,%lu,%lu\n",
            (unsigned long)warning_mm,(unsigned long)(warning_mm+20u),
            (unsigned long)warning_ui_active,(unsigned long)(now-warning_change_ms));
        reply(response);return;
    }
    if(!strcmp(line,"ENCODER_STATUS")){
        snprintf(response,sizeof(response),"ENCODER,%u,%u,%ld,%d,%lu,%lu\n",
            (unsigned)(encoder_state.phase&1u),(unsigned)((encoder_state.phase>>1)&1u),
            (long)encoder_state.cycles,(int)encoder_state.partial,
            (unsigned long)encoder_state.transitions,(unsigned long)encoder_state.invalid);
        reply(response);return;
    }
    if(!strcmp(line,"VISION_LABEL")){
        unsigned i,n;
        n=(unsigned)snprintf(response,sizeof(response),"LABEL,%lu,",(unsigned long)vision_class);
        if(vision_link_valid && vision_valid && vision_class<80){
            const uint16_t *label=vision_label_codes[vision_class];
            for(i=0;i<7 && label[i] && n+5<sizeof(response);i++)
                n+=(unsigned)snprintf(response+n,sizeof(response)-n,"%04X",(unsigned)label[i]);
        }
        response[n++]='\n';response[n]=0;reply(response);return;
    }
    if(!strcmp(line,"PHONE_STATUS")){
        snprintf(response,sizeof(response),"PHONE,%lu,%lu,%lu,%lu,%lu\n",
            (unsigned long)phone_monitor_valid,(unsigned long)phone_monitor_state,
            (unsigned long)(now-phone_monitor_last_ms),(unsigned long)vision_link_valid,
            (unsigned long)vision_valid);
        reply(response);return;
    }
    if(!strcmp(line,"RECOVERY_STATUS")){
        snprintf(response,sizeof(response),"RECOVERY,%lu,%lu,%lu,%ld,%ld,%lu,%lu,%lu,%lu\n",
            (unsigned long)range_needs_reinit,(unsigned long)range_reinit_attempts,
            (unsigned long)range_reinit_successes,(long)range_init_error,(long)range_error,
            (unsigned long)guard_state,(unsigned long)red_is_on,(unsigned long)green_is_on,
            (unsigned long)range_loaded_offset_um);
        reply(response);return;
    }
    if(!strcmp(line,"OLED2_STATUS")){
        snprintf(response,sizeof(response),"OLED2,%lu,%lu,%lu,%lu,%lu\n",
            (unsigned long)oled2_scan_count,(unsigned long)oled2_ack_3c,(unsigned long)oled2_ack_3d,
            (unsigned long)oled2_bus_error,(unsigned long)oled2_idle_lines);
        reply(response);return;
    }
    if(!strcmp(line,"OLED2_SCREEN")){
        snprintf(response,sizeof(response),"SCREEN2,%lu,%lu,%lu\n",
            (unsigned long)oled_display2_frames,(unsigned long)oled_display2_ready,
            (unsigned long)oled_display2_errors);
        reply(response);return;
    }
    if(!strcmp(line,"OLED3_STATUS")){
        snprintf(response,sizeof(response),"OLED3,%lu,%lu,%lu,%lu,%lu\n",
            (unsigned long)oled3_scan_count,(unsigned long)oled3_ack_3c,(unsigned long)oled3_ack_3d,
            (unsigned long)oled3_bus_error,(unsigned long)oled3_idle_lines);
        reply(response);return;
    }
    if(!strcmp(line,"OLED3_SCREEN")){
        snprintf(response,sizeof(response),"SCREEN3,%lu,%lu,%lu\n",
            (unsigned long)oled_display3_frames,(unsigned long)oled_display3_ready,
            (unsigned long)oled_display3_errors);
        reply(response);return;
    }
    if(!strcmp(line,"OLED_SCREEN")){
        snprintf(response,sizeof(response),"SCREEN,%lu,%lu,%lu\n",
            (unsigned long)oled_display_frames,(unsigned long)oled_display_ready,
            (unsigned long)oled_display_errors);
        reply(response);return;
    }
    if(!strcmp(line,"OLED_STATUS")){
        snprintf(response,sizeof(response),"OLED,%lu,%lu,%lu,%lu,%lu\n",
            (unsigned long)oled_scan_count,(unsigned long)oled_ack_3c,(unsigned long)oled_ack_3d,
            (unsigned long)oled_bus_error,(unsigned long)oled_idle_lines);
        reply(response);return;
    }
    if(!strcmp(line,"STATUS")){
        snprintf(response,sizeof(response),"STATUS,%lu,%lu,%ld,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu\n",
            (unsigned long)now,(unsigned long)range_rounds,(long)range_init_error,
            (unsigned long)range_status,(unsigned long)range_corrected_mm,
            (unsigned long)vision_valid,(unsigned long)vision_class,(unsigned long)vision_seq,
            (unsigned long)vision_accepted,(unsigned long)vision_rejected,(unsigned long)vision_rx_errors);
        reply(response);return;
    }
    if(strncmp(line,"V1,",3) && strncmp(line,"H1,",3))goto bad;
    star=strchr(line,'*');
    if(!star || strlen(star)!=3)goto bad;
    hi=hex_digit(star[1]);lo=hex_digit(star[2]);
    if(hi<0 || lo<0 || checksum(line,(unsigned)(star-line))!=(uint8_t)(hi*16+lo))goto bad;
    *star=0;p=line+3;
    if(line[0]=='H'){
        uint32_t state;
        if(!decimal(&p,&state,0) || state>4u)goto bad;
        phone_monitor_state=state;phone_monitor_last_ms=now;phone_monitor_valid=1;
        if(state!=3u){vision_link_valid=0;vision_valid=0;vision_class=255;}
        snprintf(response,sizeof(response),"HEART,%lu\n",(unsigned long)state);
        reply(response);return;
    }
    if(!decimal(&p,&seq,',') || !decimal(&p,&cls,',') || !decimal(&p,&score,',') ||
       !decimal(&p,&cx,',') || !decimal(&p,&cy,0))goto bad;
    if((cls>79u && cls!=255u) || score>1000u || cx>1000u || cy>1000u)goto bad;
    if(cls==255u && (score || cx || cy))goto bad;
    if(have_sequence && (int32_t)(seq-vision_seq)<=0)goto bad;
    vision_seq=seq;vision_class=cls;vision_score=score;vision_cx=cx;vision_cy=cy;
    vision_last_ms=now;vision_link_valid=1;vision_valid=cls!=255u;have_sequence=1;++vision_accepted;
    snprintf(response,sizeof(response),"ACK,%lu,%lu,%lu,%lu,%lu\n",
        (unsigned long)seq,(unsigned long)cls,(unsigned long)score,(unsigned long)cx,(unsigned long)cy);
    reply(response);return;
bad:
    ++vision_rejected;reply("ERR\n");
}

void vision_uart_poll(uint32_t now)
{
    unsigned budget=128;
    if(seen_errors!=vision_rx_errors){
        seen_errors=vision_rx_errors;line_length=0;discarding=1;
        rx_tail=rx_head;phone_monitor_valid=0;vision_link_valid=0;vision_valid=0;vision_class=255;
    }
    while(budget-- && rx_tail!=rx_head){
        uint8_t byte=rx[rx_tail];rx_tail=(rx_tail+1u)&255u;
        if(byte=='\n'){
            if(!discarding && line_length){line[line_length]=0;accept_line(line,now);}
            else if(discarding)++vision_rejected;
            line_length=0;discarding=0;
        }else if(byte!='\r' && !discarding){
            if(byte<32 || byte>126 || line_length>=sizeof(line)-1){discarding=1;line_length=0;}
            else line[line_length++]=(char)byte;
        }
    }
    /* No stale target may survive a disconnected or stalled sender. */
    if((uint32_t)(now-vision_last_ms)>=2000u){vision_link_valid=0;vision_valid=0;vision_class=255;}
    if((uint32_t)(now-phone_monitor_last_ms)>=3500u)phone_monitor_valid=0;
    budget=16;
    while(budget-- && tx_tail!=tx_head && USART_GetFlagStatus(USART1,USART_FLAG_TXE)==SET){
        USART_SendData(USART1,tx[tx_tail]);tx_tail=(tx_tail+1u)&255u;
    }
}

/* Only the main loop calls this synchronous query adapter. UART ISR only
 * queues bytes; USB commands never overwrite an unfinished UART line. */
int vision_usb_query(const char *text,uint32_t now,void (*send)(const char *))
{
    static const char *const queries[]={
        "PING","STATUS","GIMBAL_STATUS","ULTRA_STATUS",
        "GIMBAL_MANUAL_START","GIMBAL_KEEPALIVE","GIMBAL_STOP",
        "OLED_STATUS","OLED2_STATUS","OLED3_STATUS",
        "OLED_SCREEN","OLED2_SCREEN","OLED3_SCREEN",
        "MUTE_STATUS","SETTINGS_STATUS","RECOVERY_STATUS","PARAM_STATUS",
        "TREND_STATUS","PHONE_STATUS","MOTOR_STATUS","MOTOR_DASH_STATUS"
    };
    char message[96];unsigned i;
    if(!send)return 0;
    if(!text||strlen(text)>=sizeof(message)||usb_reply_sink){send("ERR,USB_READ_ONLY\n");return 0;}
    for(i=0;i<sizeof(queries)/sizeof(queries[0]);i++)if(!strcmp(text,queries[i]))break;
    if(i==sizeof(queries)/sizeof(queries[0])){
        uint32_t yaw,pitch;const char *cursor=text;
        if(strncmp(text,"GIMBAL_SET,",11)){
            send("ERR,USB_COMMAND_REJECTED\n");return 0;
        }
        cursor+=11;
        if(!decimal(&cursor,&yaw,',')||
           !decimal(&cursor,&pitch,0)||!manual_target_valid(yaw,pitch)){
            send("ERR,USB_COMMAND_REJECTED\n");return 0;
        }
    }
    strcpy(message,text);usb_reply_sink=send;
    accept_line(message,now);
    usb_reply_sink=0;return 1;
}
