/* Included inside motor_probe.c after its existing passive-query helpers.
 * Retry a missed boot profile / lost passive upload ONLY while drive is off.
 * No parameter setting command, ARM or motor speed/PWM action is issued. */
static uint8_t profile_recovery_phase;
static uint32_t profile_recovery_attempt,profile_recovery_began;
static void motor_profile_recovery_poll(uint32_t now)
{
    int voltage_fresh=motor_voltage_frames &&
        (uint32_t)(now-motor_voltage_last_ms)<2500u &&
        motor_voltage_mv>=6000u && motor_voltage_mv<=8500u;
    int speed_fresh=motor_speed_frames && (uint32_t)(now-motor_speed_last_ms)<1500u;
    if(remote_drive_armed || motor_pulse_active)return;
    if(!profile_recovery_phase){
        if(!profile_boot_sent || motor_parameter_capture || !motor_monitor_enabled ||
           !voltage_fresh || (motor_profile_ready && speed_fresh) ||
           (uint32_t)(now-profile_recovery_attempt)<5000u)return;
        if(motor_monitor(now,0)){
            motor_profile_ready=0;
            profile_recovery_phase=1;profile_recovery_began=profile_recovery_attempt=now;
        }
    }else if(profile_recovery_phase==1){
        if(voltage_fresh && (uint32_t)(now-profile_recovery_began)>=150u && motor_parameter_read(now)){
            /* Existing capture completion validates the real flash profile.
             * Restore passive uploads only after capture has drained. */
            motor_monitor_enabled=1;upload_boot_configured=0;profile_recovery_phase=2;
        }
    }else if(!motor_parameter_capture){
        profile_recovery_phase=0;profile_recovery_attempt=now;
    }
}
