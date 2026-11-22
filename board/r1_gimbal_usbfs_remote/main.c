#include "UART.h"
extern void native_usb_poll(uint32_t now);
#include "motor_probe.h"
#include "ultrasonic.h"
#include "servo_probe.h"
#include "debug.h"
#include "vl53l0x_api.h"
#include <string.h>
#include "app.h"
#include "vision_uart.h"
#include "oled_probe.h"
#include "oled_display.h"
#include "oled_probe2.h"
#include "oled_display2.h"
#include "oled_probe3.h"
#include "oled_display3.h"
#include "encoder_decode.h"
#include "warning_adjust.h"
#include "distance_trend.h"
#include "user_key.h"
#include "settings.h"
#include "storage_probe.h"
static user_key_t mute_key;
static volatile uint32_t user_key_ready;
volatile uint32_t save_key_requests,save_request_mm,save_request_muted;
volatile uint32_t buzzer_muted,mute_key_presses,mute_key_level=1;
static distance_trend_t trend;
volatile uint32_t trend_valid,trend_kind,trend_samples;
volatile int32_t trend_closing_mm_s;
volatile uint32_t warning_mm=200,warning_change_ms,warning_ui_active;
volatile encoder_decode_t encoder_state;
/* EC11 removed: diagnostic struct stays zeroed for serial compatibility. */

/* Desk warning prototype: experimental white-target correction, not a
 * generally validated accuracy claim. Keep original readings for diagnosis. */
static VL53L0X_Dev_t device;
volatile uint32_t range_stage, range_rounds, range_valid_count;
volatile int32_t range_init_error, range_error;
volatile uint32_t range_status=255, range_mm=0xFFFFFFFFu, range_model_id;
typedef struct { uint32_t round, mm, status; int32_t error; } RangeRecord;
volatile RangeRecord range_history[32];
volatile uint32_t range_history_count;
volatile uint32_t range_corrected_mm=0xFFFFFFFFu, range_correction_valid, range_in_calibrated_interval;
volatile int32_t range_loaded_offset_um;

/* MCU resets do not necessarily power-cycle the sensor. Follow ST's soft
 * reset sequence with bounded waits instead of its unbounded reference loops. */
static VL53L0X_Error reset_sensor(void)
{
    unsigned i;
    uint8_t id=0xFF;
    VL53L0X_Error e=VL53L0X_WrByte(&device,VL53L0X_REG_SOFT_RESET_GO2_SOFT_RESET_N,0);
    if(e)return e;
    for(i=0;i<100;i++){
        e=VL53L0X_RdByte(&device,VL53L0X_REG_IDENTIFICATION_MODEL_ID,&id);
        if(!e && id==0)break;
        Delay_Ms(1);
    }
    /* Always release reset even when the first wait failed. */
    e=VL53L0X_WrByte(&device,VL53L0X_REG_SOFT_RESET_GO2_SOFT_RESET_N,1);
    if(e)return e;
    if(i==100)return VL53L0X_ERROR_TIME_OUT;
    for(i=0;i<100;i++){
        e=VL53L0X_RdByte(&device,VL53L0X_REG_IDENTIFICATION_MODEL_ID,&id);
        if(!e && id==0xEE)return VL53L0X_ERROR_NONE;
        Delay_Ms(1);
    }
    return VL53L0X_ERROR_TIME_OUT;
}
static VL53L0X_Error initialize(void)
{
    VL53L0X_Error e;
    uint8_t id=0, vhv, phase, aperture;
    uint32_t spads;
    int32_t loaded_offset=0;
    memset(&device,0,sizeof(device));
    range_loaded_offset_um=0;
    device.I2cDevAddr=0x52;
    range_stage=1;
    e=VL53L0X_RdByte(&device,0xC0,&id); range_model_id=id;
    if(e || id!=0xEE) return e ? e : VL53L0X_ERROR_NOT_SUPPORTED;
    range_stage=9; e=reset_sensor(); if(e)return e;
    range_stage=2; e=VL53L0X_DataInit(&device); if(e)return e;
    range_stage=3; e=VL53L0X_StaticInit(&device); if(e)return e;
    range_stage=4; e=VL53L0X_PerformRefSpadManagement(&device,&spads,&aperture); if(e)return e;
    range_stage=5; e=VL53L0X_PerformRefCalibration(&device,&vhv,&phase); if(e)return e;
    range_stage=6; e=VL53L0X_SetDeviceMode(&device,VL53L0X_DEVICEMODE_SINGLE_RANGING); if(e)return e;
    range_stage=7; e=VL53L0X_SetMeasurementTimingBudgetMicroSeconds(&device,33000); if(e)return e;
    range_stage=10;
    e=VL53L0X_SetOffsetCalibrationDataMicroMeter(&device,13000); if(e)return e;
    e=VL53L0X_GetOffsetCalibrationDataMicroMeter(&device,&loaded_offset); if(e)return e;
    range_loaded_offset_um=loaded_offset;
    if(loaded_offset!=13000)return VL53L0X_ERROR_CONTROL_INTERFACE;
    range_stage=8; return VL53L0X_ERROR_NONE;
}

static app_t application;
/* Desk demonstration only. Hysteresis prevents chatter near boundaries. */
static const guard_config_t desk_config={80u,110u,200u,220u,300u,3u};
volatile uint32_t tick_ms, led_mode=GUARD_FAULT, led_last_good_ms;
volatile uint32_t guard_state=GUARD_FAULT, guard_fault=GUARD_FAULT_NO_DATA;
volatile uint32_t led_is_on, led_edges, red_is_on, red_edges, app_ticks, sensor_pending;
volatile uint32_t green_is_on, green_edges;
volatile uint32_t buzzer_is_on, buzzer_edges;
volatile uint32_t timer_clock_hz, timer_prescaler;
static uint32_t last_sensor_start_ms, last_sensor_poll_ms;
static bool attempted;
volatile uint32_t range_needs_reinit, range_reinit_attempts, range_reinit_successes;
volatile uint32_t range_last_reinit_ms;

/* Q24 phase accumulator keeps pulse progress when distance/frequency changes.
 * Never recompute phase as now % new_period: that introduces false edges. */
#define LED_PHASE_CYCLE (1u<<24)
volatile uint32_t led_period_ms=800u, led_phase_step=LED_PHASE_CYCLE/800u;
volatile uint32_t led_phase_q24, led_filtered_distance_q8;
static uint32_t filter_sample_count;
static bool filter_initialized;

void TIM2_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
void TIM2_IRQHandler(void)
{
    uint32_t now, mode;
    bool on=false, red_on=false, green_on=false, audible;
    if(TIM_GetITStatus(TIM2,TIM_IT_Update)!=SET)return;
    TIM_ClearITPendingBit(TIM2,TIM_IT_Update);
    now=++tick_ms;
    ultrasonic_tick(now);
    servo_probe_tick(now);
    /* No knob sampling: disconnected PD4/PD5 cannot change the warning distance. */
    mute_key_level=(GPIOA->INDR>>4)&1u;
    if(user_key_ready){uint8_t event=user_key_sample(&mute_key,(uint8_t)mute_key_level);
     if(event==1)buzzer_muted^=1u;else if(event==2){save_request_mm=warning_mm;save_request_muted=buzzer_muted;++save_key_requests;}}
    mute_key_presses=mute_key.presses;
    mode=led_mode;
    /* Independent of application/bus progress: never display a stale NORMAL. */
    if((uint32_t)(now-led_last_good_ms)>=300u)mode=GUARD_FAULT;
    if(mode==GUARD_CAUTION || mode==GUARD_DANGER){
        led_phase_q24=(led_phase_q24+led_phase_step)&(LED_PHASE_CYCLE-1u);
        on=led_phase_q24<(LED_PHASE_CYCLE/2u);
    }else{
        led_phase_q24=0u;
        green_on=mode==GUARD_NORMAL;
        /* Unknown/stale data never displays green; fault is steady red. */
        red_on=!green_on;
    }
    if(led_is_on!=(uint32_t)on)++led_edges;
    led_is_on=on;
    /* External two-lead LEDs, each with its OWN1k series resistor:
     * 3V3 -> resistor -> LED anode(long) -> cathode(short) -> PD0/PD1/PD2.
     * Outputs sink current: LOW=ON. Remove old LED1 -> PD0 jumper when wired. */
    if(on)GPIO_ResetBits(GPIOD,GPIO_Pin_0);else GPIO_SetBits(GPIOD,GPIO_Pin_0);
    if(red_is_on!=(uint32_t)red_on)++red_edges;
    red_is_on=red_on;
    if(red_on)GPIO_ResetBits(GPIOD,GPIO_Pin_1);else GPIO_SetBits(GPIOD,GPIO_Pin_1);
    if(green_is_on!=(uint32_t)green_on)++green_edges;
    green_is_on=green_on;
    if(green_on)GPIO_ResetBits(GPIOD,GPIO_Pin_2);else GPIO_SetBits(GPIOD,GPIO_Pin_2);
    /* Active-low MODULE control input (not a bare buzzer): PD3 drives IO.
     * VCC uses3V3 for the first compatibility test; GND shares board ground.
     * Follow blue warning pulses; far, initialization and fault stay silent. */
    audible=on && !buzzer_muted;
    if(buzzer_is_on!=(uint32_t)audible)++buzzer_edges;
    buzzer_is_on=audible;
    if(audible)GPIO_ResetBits(GPIOD,GPIO_Pin_3);else GPIO_SetBits(GPIOD,GPIO_Pin_3);
}

static void clock_init(void)
{
    RCC_ClocksTypeDef clocks;
    TIM_TimeBaseInitTypeDef timer={0};
    NVIC_InitTypeDef irq={0};
    RCC_GetClocksFreq(&clocks);
    timer_clock_hz=clocks.PCLK1_Frequency;
    if(clocks.PCLK1_Frequency!=clocks.HCLK_Frequency)timer_clock_hz*=2u;
    timer_prescaler=timer_clock_hz/1000000u-1u;
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM2,ENABLE);
    timer.TIM_Period=999;
    timer.TIM_Prescaler=(uint16_t)timer_prescaler;
    timer.TIM_ClockDivision=TIM_CKD_DIV1;
    timer.TIM_CounterMode=TIM_CounterMode_Up;
    TIM_TimeBaseInit(TIM2,&timer);
    TIM_ClearITPendingBit(TIM2,TIM_IT_Update);
    irq.NVIC_IRQChannel=TIM2_IRQn;
    irq.NVIC_IRQChannelPreemptionPriority=0;
    irq.NVIC_IRQChannelSubPriority=1;
    irq.NVIC_IRQChannelCmd=ENABLE;
    NVIC_Init(&irq);
    TIM_ITConfig(TIM2,TIM_IT_Update,ENABLE);
    TIM_Cmd(TIM2,ENABLE);
}

static uint32_t millis(void *context){(void)context;return tick_ms;}
static app_sample_t record_sample(VL53L0X_Error error,
                                 const VL53L0X_RangingMeasurementData_t *measurement)
{
    app_sample_t sample={true,false,0};
    uint32_t index;
    range_error=error;
    /* A transport/shot timeout can leave both bus and device state invalid.
     * RangeStatus quality failures alone do not reset a functioning sensor. */
    if(error){range_needs_reinit=1;range_loaded_offset_um=0;}

    range_status=measurement ? measurement->RangeStatus : 255u;
    range_mm=(!error && measurement) ? measurement->RangeMilliMeter : 0xFFFFFFFFu;
    range_correction_valid=(!error && !range_status && range_loaded_offset_um==13000);
    range_corrected_mm=range_correction_valid ? (range_mm*1000u+13000u+565u)/1130u : 0xFFFFFFFFu;
    range_in_calibrated_interval=range_correction_valid && range_mm>=100u && range_mm<=326u;
    ++range_rounds;
    if(range_correction_valid)++range_valid_count;
    index=range_history_count%32u;
    range_history[index].round=range_rounds;
    range_history[index].mm=range_mm;
    range_history[index].status=range_status;
    range_history[index].error=range_error;
    ++range_history_count;
    sample.valid=range_correction_valid && range_corrected_mm<=65535u;
    sample.distance_mm=sample.valid ? (uint16_t)range_corrected_mm : 0u;
    distance_trend_sample(&trend,tick_ms,sample.valid,sample.distance_mm);
    return sample;
}

static app_sample_t read_sensor(void *context)
{
    app_sample_t absent={false,false,0};
    VL53L0X_RangingMeasurementData_t measurement;
    VL53L0X_Error error;
    uint8_t ready=0;
    uint32_t now=tick_ms;
    (void)context;
    if(range_needs_reinit || range_init_error){
        if((uint32_t)(now-range_last_reinit_ms)<1000u)return absent;
        range_last_reinit_ms=now;++range_reinit_attempts;
        sensor_pending=0;range_correction_valid=0;range_corrected_mm=0xFFFFFFFFu;
        range_init_error=range_bus_recover();
        if(!range_init_error)range_init_error=initialize();
        range_needs_reinit=range_init_error!=0;
        /* Space retries from completion; no tight loop on missing wires. */
        range_last_reinit_ms=tick_ms;
        if(range_init_error)return record_sample(range_init_error,0);
        ++range_reinit_successes;
        attempted=false;
        return absent; /* Guard stays FAULT until three NEW valid shots. */
    }
    if(!sensor_pending){
        if(attempted && (uint32_t)(now-last_sensor_start_ms)<100u)return absent;
        attempted=true;
        last_sensor_start_ms=now;
        if(range_init_error)return record_sample(range_init_error,0);
        error=VL53L0X_StartMeasurement(&device);
        if(error)return record_sample(error,0);
        sensor_pending=1;
        last_sensor_poll_ms=tick_ms;
        return absent;
    }
    if((uint32_t)(now-last_sensor_poll_ms)<5u)return absent;
    last_sensor_poll_ms=now;
    error=VL53L0X_GetMeasurementDataReady(&device,&ready);
    if(!error && !ready){
        if((uint32_t)(tick_ms-last_sensor_start_ms)<150u)return absent;
        error=VL53L0X_ERROR_TIME_OUT;
    }
    if(error){
        sensor_pending=0;
        /* End failed shot before scheduled bus/device reinitialization. */
        VL53L0X_StopMeasurement(&device);
        VL53L0X_ClearInterruptMask(&device,0);
        return record_sample(error,0);
    }
    memset(&measurement,0,sizeof(measurement));
    measurement.RangeStatus=255;
    error=VL53L0X_GetRangingMeasurementData(&device,&measurement);
    if(!error)error=VL53L0X_ClearInterruptMask(&device,0);
    sensor_pending=0;
    return record_sample(error,&measurement);
}

static void write_output(void *context,guard_output_t output)
{
    (void)context;(void)output;
    /* NORMAL is steady green; both close states use the same blue cadence. */
    /* Update once per NEW valid result, never once per main-loop tick.
     * Half-weight EMA (~0.1-0.3s settling) suppresses stationary reading jitter.
     * Filtering affects indication only; guard still consumes unfiltered values. */
    if(range_correction_valid && filter_sample_count!=range_valid_count){
        uint32_t target_q8=range_corrected_mm*256u;
        uint32_t period;
        filter_sample_count=range_valid_count;
        if(!filter_initialized){
            led_filtered_distance_q8=target_q8;
            filter_initialized=true;
        }else{
            led_filtered_distance_q8=(led_filtered_distance_q8+target_q8+1u)/2u;
        }
        /* period_ms = 4 * distance_mm, clamped only at physical UI limits.
         * 50mm->200ms;100mm->400ms;200mm->800ms;300mm->1200ms.
         * Timer resolution is1ms: approximately continuous, not analogue. */
        period=(led_filtered_distance_q8+32u)/64u;
        if(period<160u)period=160u;
        if(period>1200u)period=1200u;
        led_period_ms=period;
        led_phase_step=LED_PHASE_CYCLE/period;
    }
    led_last_good_ms=application.guard.last_good_ms;
    guard_fault=application.guard.fault;
    guard_state=application.guard.state;
    if(guard_state==GUARD_FAULT)filter_initialized=false;
    led_mode=guard_state;
}

int main(void)
{
    GPIO_InitTypeDef gpio={0};
    const app_ports_t ports={millis,read_sensor,write_output};
    uint32_t last_tick,seen_save_requests=0;
    guard_config_t initial_config=desk_config;

    uint8_t screen_turn=0;
    NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);
    SystemCoreClockUpdate();Delay_Init();vision_uart_init();motor_probe_init();
    range_bus_init();
    oled_probe_init();
    oled_probe2_init();
    oled_probe3_init();
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOD,ENABLE);
    GPIO_SetBits(GPIOD,GPIO_Pin_0|GPIO_Pin_1|GPIO_Pin_2|GPIO_Pin_3);
    gpio.GPIO_Pin=GPIO_Pin_0|GPIO_Pin_1|GPIO_Pin_2|GPIO_Pin_3;gpio.GPIO_Mode=GPIO_Mode_Out_PP;gpio.GPIO_Speed=GPIO_Speed_2MHz;
    GPIO_Init(GPIOD,&gpio);
    /* PD4/PD5 are no longer allocated to EC11. Do not read or drive them. */
    encoder_decode_init(&encoder_state,3u);
    /* R1 USER/KEY requires the physical KEY -> PA4 jumper; input pull-up. */
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA,ENABLE);
    gpio.GPIO_Pin=GPIO_Pin_4;gpio.GPIO_Mode=GPIO_Mode_IPU;GPIO_Init(GPIOA,&gpio);
    user_key_init(&mute_key,(uint8_t)((GPIOA->INDR>>4)&1u));
    clock_init();
    ultrasonic_init();
    servo_probe_init();
    Delay_Ms(100);
    storage_probe_init();
    settings_init(tick_ms);
    if(settings_loaded){buzzer_muted=settings_saved_muted;warning_mm=settings_saved_mm;initial_config.caution_on_mm=(uint16_t)warning_mm;initial_config.caution_off_mm=(uint16_t)(warning_mm+20u);}
    range_init_error=range_bus_recover();
    if(!range_init_error)range_init_error=initialize();
    range_needs_reinit=range_init_error!=0;range_last_reinit_ms=tick_ms;
    if(!app_init(&application,&ports,0,&initial_config))for(;;);
    /* Arm input only after boot restoration and peripheral initialization.
     * Ignore boot-held keys until released; initialization is never a short press. */
    user_key_init(&mute_key,(uint8_t)((GPIOA->INDR>>4)&1u));
    user_key_ready=1;
    /* P7 USBFS is independent of P9 USART1. No UART2 or TIM2 USB bridge. */
    UART2_ParaInit(1);USBFS_RCC_Init();USBFS_Device_Init(ENABLE);
    NVIC_InitTypeDef usb_irq={0};
    usb_irq.NVIC_IRQChannel=USBFS_IRQn;usb_irq.NVIC_IRQChannelPreemptionPriority=2;
    usb_irq.NVIC_IRQChannelSubPriority=1;usb_irq.NVIC_IRQChannelCmd=ENABLE;NVIC_Init(&usb_irq);
    last_tick=tick_ms-1u;
    for(;;){
        /* Warning distance comes from defaults/restored settings, not a knob. */
        if(warning_ui_active && (uint32_t)(tick_ms-warning_change_ms)>=5000u)warning_ui_active=0;
        if(save_key_requests!=seen_save_requests){seen_save_requests=save_key_requests;settings_request((uint16_t)save_request_mm,(uint8_t)save_request_muted,tick_ms);}
        ultrasonic_poll(tick_ms);
        settings_poll(tick_ms);
        vision_uart_poll(tick_ms);
        native_usb_poll(tick_ms);
        motor_probe_poll(tick_ms);
        oled_probe_poll(tick_ms);
        oled_probe2_poll(tick_ms);
        oled_probe3_poll(tick_ms);
        /* One screen chunk per loop, keeping UART and ToF serviced. */
        if(screen_turn==0)oled_display_poll(tick_ms);
        else if(screen_turn==1)oled_display2_poll(tick_ms);
        else oled_display3_poll(tick_ms);
        screen_turn=(screen_turn+1u)%3u;
        if(last_tick!=tick_ms){
            last_tick=tick_ms;
            app_tick(&application);
            ++app_ticks;
            if(application.guard.state==GUARD_FAULT)distance_trend_reset(&trend);
            else distance_trend_expire(&trend,tick_ms);
            trend_valid=trend.valid;trend_kind=trend.kind;
            trend_closing_mm_s=trend.closing_mm_s;trend_samples=trend.count;
        }
    }
}
