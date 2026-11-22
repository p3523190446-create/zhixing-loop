#include "startup_gate.h"
/* Object-only compile harness; no main, GPIO or actuator calls. */
void compile_startup_gate_api(startup_gate_t *s, uint32_t now)
{
    startup_gate_init(s, STARTUP_PHONE_OTG_DIAGNOSTIC);
    startup_gate_note_valid_link(s, now);
    startup_gate_note_sensor(s, now, true, true);
    startup_gate_note_driver(s, now, true);
    startup_gate_tick(s, now);
    (void)startup_gate_request_gimbal(s, now);
    (void)startup_gate_request_vehicle(s, now);
    startup_gate_fault(s, now);
    startup_gate_stop(s, now);
}
