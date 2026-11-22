"""Move only the gimbal PWM hardware to PA0/TIM5_CH1, PA1/TIM5_CH2."""
import hashlib,json,shutil
import build_r1_motor_run_live_voltage as previous
import build_r1_drive_bench as helpers
build=previous.build
build.STEM='r1_gimbal_tim5';build.WORK=build.TOOLS/'r1-gimbal-tim5'
build.OUT=build.PROJECT/'知行回路软件/build/r1_gimbal_tim5'
base_prepare=build.PREPARE
INIT='''void servo_probe_init(void)
{
    GPIO_InitTypeDef gpio={0};TIM_TimeBaseInitTypeDef timer={0};
    TIM_OCInitTypeDef compare={0};RCC_ClocksTypeDef clocks;
    uint32_t timer_clock;
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA|RCC_APB2Periph_AFIO,ENABLE);
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM5,ENABLE);
    RCC_GetClocksFreq(&clocks);timer_clock=clocks.PCLK1_Frequency;
    if(clocks.PCLK1_Frequency!=clocks.HCLK_Frequency)timer_clock*=2u;
    /* PA0/PA1 default TIM5_CH1/CH2; TIM2 safety and TIM4 ranging untouched. */
    TIM_Cmd(TIM5,DISABLE);
    GPIO_ResetBits(GPIOA,GPIO_Pin_0|GPIO_Pin_1);
    gpio.GPIO_Pin=GPIO_Pin_0|GPIO_Pin_1;gpio.GPIO_Mode=GPIO_Mode_AF_PP;
    gpio.GPIO_Speed=GPIO_Speed_2MHz;GPIO_Init(GPIOA,&gpio);
    timer.TIM_Prescaler=(uint16_t)(timer_clock/1000000u-1u);timer.TIM_Period=19999u;
    timer.TIM_CounterMode=TIM_CounterMode_Up;timer.TIM_ClockDivision=TIM_CKD_DIV1;
    TIM_TimeBaseInit(TIM5,&timer);
    state.yaw_hz=state.pitch_hz=timer_clock/(timer.TIM_Prescaler+1u);
    compare.TIM_OCMode=TIM_OCMode_PWM1;compare.TIM_OutputState=TIM_OutputState_Enable;
    compare.TIM_Pulse=0;compare.TIM_OCPolarity=TIM_OCPolarity_High;
    TIM_OC1Init(TIM5,&compare);TIM_OC2Init(TIM5,&compare);
    TIM_OC1PreloadConfig(TIM5,TIM_OCPreload_Enable);TIM_OC2PreloadConfig(TIM5,TIM_OCPreload_Enable);
    TIM_ARRPreloadConfig(TIM5,ENABLE);TIM_GenerateEvent(TIM5,TIM_EventSource_Update);
    TIM_Cmd(TIM5,ENABLE);
    state.ready=state.yaw_hz==1000000u && state.pitch_hz==1000000u;
    /* Both channels boot at zero; manual control still requires explicit start. */
}
'''
def prepare():
 base_prepare();u=build.WORK/'User'
 helpers.edit(u/'servo_probe.c','TIM_SetCompare1(TIM1,p.yaw);TIM_SetCompare3(TIM3,p.pitch);',
              'TIM_SetCompare1(TIM5,p.yaw);TIM_SetCompare2(TIM5,p.pitch);')
 p=u/'servo_probe.c';s=p.read_text(encoding='utf8');a=s.index('void servo_probe_init(void)');b=s.index('int servo_probe_start(',a)
 p.write_text(s[:a]+INIT+s[b:],encoding='utf8')
 helpers.edit(u/'vision_uart.c','    if(!strcmp(line,"GIMBAL_STATUS")){',
 '''    if(!strcmp(line,"GIMBAL_PINS")){reply("GIMBAL_PINS,PA0,PA1,TIM5_CH1_CH2\\n");return;}
    if(!strcmp(line,"GIMBAL_HW")){
        snprintf(response,sizeof(response),"GIMBAL_HW,%lu,%lu,%lu,%lu,%lu,%lu,%lu\\n",
            (unsigned long)TIM5->PSC,(unsigned long)TIM5->ATRLR,
            (unsigned long)TIM5->CH1CVR,(unsigned long)TIM5->CH2CVR,
            (unsigned long)TIM5->CCER,(unsigned long)TIM5->CTLR1,
            (unsigned long)(GPIOA->CFGLR&255u));reply(response);return;
    }
    if(!strcmp(line,"GIMBAL_STATUS")){''')
 helpers.edit(u/'remote_drive.c','R1_MOTOR_RUN_LIVE_VOLTAGE_20261020','R1_GIMBAL_TIM5_20261020')
build.PREPARE=prepare
if __name__=='__main__':
 build.main();snapshot=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snapshot,dirs_exist_ok=True)
 baseline=build.PROJECT/'知行回路软件/build/r1_motor_run_live_voltage/source-snapshot'
 changed=[x.relative_to(snapshot).as_posix() for x in snapshot.rglob('*') if x.is_file() and (not (baseline/x.relative_to(snapshot)).exists() or x.read_bytes()!=(baseline/x.relative_to(snapshot)).read_bytes())]
 assert sorted(changed)==['remote_drive.c','servo_probe.c','vision_uart.c'],changed
 p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
 d.update(date='2026-10-20',scope='Only gimbal hardware moves PA8/TIM1+PB0/TIM3 to PA0/PA1 TIM5; 1MHz,20ms PWM; same manual bounds/3s lease/boot zero; motor/TIM2/TIM4/USB/Android protocol unchanged',changed_sources=changed,flash='NOT_RUN',physical_acceptance='NOT_RUN',all_source_sha256={x.relative_to(snapshot).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snapshot.rglob('*') if x.suffix in ('.c','.h')})
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(d['binary_sha256'])
