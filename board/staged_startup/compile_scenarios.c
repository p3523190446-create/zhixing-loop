#define inline inline __attribute__((always_inline))
#include "startup_gate.h"
#undef inline
/* Compile-time constant scenarios evaluated by the real MCU C compiler.
 * No hardware or runtime execution; the error attribute rejects a failed rule. */
extern void startup_scenario_failed(void) __attribute__((error("startup permission scenario failed")));
#define EXPECT(c) do { if (!(c)) startup_scenario_failed(); } while (0)
static inline __attribute__((always_inline)) void warm(startup_gate_t *s)
{
    startup_gate_note_valid_link(s, 10); startup_gate_tick(s, 10);
    startup_gate_note_valid_link(s, 20); startup_gate_tick(s, 20);
    startup_gate_note_valid_link(s, 30); startup_gate_tick(s, 30);
}
void verify_startup_scenarios(void)
{
    startup_gate_t s;
    startup_gate_init(&s, STARTUP_VEHICLE_EXTERNAL_POWER);
    EXPECT(!s.permit_gimbal && !s.permit_vehicle && s.stage == STARTUP_SAFE_IDLE);
    s.servo_power_verified = s.vehicle_power_verified = true;
    EXPECT(!startup_gate_request_gimbal(&s, 0));
    warm(&s);
    EXPECT(s.stage == STARTUP_LINK_READY && s.link_messages == 3);
    EXPECT(!s.permit_gimbal && !s.permit_vehicle);
    startup_gate_note_sensor(&s, 30, true, true); startup_gate_note_driver(&s, 30, true);
    EXPECT(startup_gate_request_gimbal(&s, 30));
    EXPECT(startup_gate_request_vehicle(&s, 30));
    EXPECT(s.stage == STARTUP_VEHICLE_READY);
    startup_gate_note_sensor(&s, 31, true, false); startup_gate_tick(&s, 31);
    EXPECT(!s.permit_vehicle && s.permit_gimbal);
    startup_gate_note_sensor(&s, 32, true, true); startup_gate_tick(&s, 32);
    EXPECT(!s.permit_vehicle); /* obstacle clearing cannot restart the vehicle */
    EXPECT(startup_gate_request_vehicle(&s, 32));
    startup_gate_tick(&s, 1531);
    EXPECT(!s.permit_vehicle && !s.permit_gimbal && s.link_messages == 0);
    startup_gate_note_valid_link(&s, 1600); startup_gate_note_valid_link(&s, 1610);
    startup_gate_note_valid_link(&s, 1620); startup_gate_tick(&s, 1620);
    EXPECT(s.stage == STARTUP_LINK_READY && !s.permit_vehicle && !s.permit_gimbal);

    startup_gate_init(&s, STARTUP_PHONE_OTG_DIAGNOSTIC); warm(&s);
    s.servo_power_verified = s.vehicle_power_verified = true;
    startup_gate_note_sensor(&s, 30, true, true); startup_gate_note_driver(&s, 30, true);
    EXPECT(!startup_gate_request_gimbal(&s, 30));
    EXPECT(!startup_gate_request_vehicle(&s, 30));

    startup_gate_init(&s, STARTUP_COMPUTER_BENCH); warm(&s);
    EXPECT(!startup_gate_request_gimbal(&s, 30)); /* no power qualification */
    s.servo_power_verified = s.vehicle_power_verified = true;
    startup_gate_note_sensor(&s, 30, true, true); startup_gate_note_driver(&s, 30, true);
    EXPECT(startup_gate_request_gimbal(&s, 30));
    EXPECT(!startup_gate_request_vehicle(&s, 30));
    startup_gate_stop(&s, 31); EXPECT(!s.permit_gimbal && s.stage == STARTUP_LINK_READY);

    startup_gate_init(&s, STARTUP_VEHICLE_EXTERNAL_POWER); warm(&s);
    s.vehicle_power_verified = true;
    startup_gate_note_sensor(&s, 30, true, true); startup_gate_note_driver(&s, 30, true);
    EXPECT(!startup_gate_request_vehicle(&s, 331)); /* stale sensor */
    startup_gate_note_sensor(&s, 531, true, true);
    EXPECT(!startup_gate_request_vehicle(&s, 531)); /* stale driver */
    startup_gate_note_driver(&s, 531, true); EXPECT(startup_gate_request_vehicle(&s, 531));
    startup_gate_fault(&s, 532); EXPECT(!s.permit_vehicle && s.stage == STARTUP_FAULT);

    startup_gate_init(&s, (startup_profile_t)99); warm(&s);
    s.servo_power_verified = s.vehicle_power_verified = true;
    EXPECT(!startup_gate_request_gimbal(&s, 30));
    EXPECT(!startup_gate_request_vehicle(&s, 30));

    startup_gate_init(&s, STARTUP_COMPUTER_BENCH); s.servo_power_verified = true;
    startup_gate_note_valid_link(&s, UINT32_MAX - 32);
    startup_gate_note_valid_link(&s, UINT32_MAX - 31);
    startup_gate_note_valid_link(&s, UINT32_MAX - 30);
    EXPECT(startup_gate_request_gimbal(&s, 50)); /* uint32 clock wrap */
}
