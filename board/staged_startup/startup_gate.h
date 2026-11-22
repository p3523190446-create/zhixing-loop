#ifndef ZXR_STARTUP_GATE_H
#define ZXR_STARTUP_GATE_H
#include <stdint.h>
#include <stdbool.h>
#include <string.h>

/* Prepared MCU permission module. Not yet integrated/flashed.
 * This controls permission to emit actuator signals, not the +5V power rail.
 * Call only from the MCU's validated protocol/main-loop path. */
typedef enum {
    STARTUP_PHONE_OTG_DIAGNOSTIC = 0,
    STARTUP_COMPUTER_BENCH = 1,
    STARTUP_VEHICLE_EXTERNAL_POWER = 2
} startup_profile_t;
typedef enum {
    STARTUP_SAFE_IDLE = 0, STARTUP_LINK_READY = 1,
    STARTUP_GIMBAL_READY = 2, STARTUP_VEHICLE_READY = 3,
    STARTUP_FAULT = 4
} startup_stage_t;
typedef struct {
    startup_profile_t profile;
    startup_stage_t stage;
    uint32_t link_at, sensor_at, driver_at;
    uint8_t link_messages;
    bool fault, sensor_valid, distance_clear, driver_valid;
    bool servo_power_verified, vehicle_power_verified;
    bool request_gimbal, request_vehicle;
    bool permit_gimbal, permit_vehicle;
} startup_gate_t;

#define STARTUP_LINK_MAX_AGE_MS 1500u
#define STARTUP_SENSOR_MAX_AGE_MS 300u
#define STARTUP_DRIVER_MAX_AGE_MS 500u

static inline void startup_gate_init(startup_gate_t *s, startup_profile_t profile)
{
    memset(s, 0, sizeof(*s));
    s->profile = profile;
    s->stage = STARTUP_SAFE_IDLE;
}
static inline bool startup_gate_link_ready(const startup_gate_t *s, uint32_t now)
{
    return s->link_messages >= 3u && (uint32_t)(now - s->link_at) <= STARTUP_LINK_MAX_AGE_MS;
}
static inline void startup_gate_note_valid_link(startup_gate_t *s, uint32_t now)
{
    /* Caller has checked message format, sequence, expiry and authorization.
     * USB accepted TX or an unparsed byte must never call this function. */
    if (s->link_messages && (uint32_t)(now - s->link_at) > STARTUP_LINK_MAX_AGE_MS) {
        s->link_messages = 0; s->request_gimbal = s->request_vehicle = false;
        s->permit_gimbal = s->permit_vehicle = false;
    }
    s->link_at = now;
    if (s->link_messages < 3u) ++s->link_messages;
}
static inline void startup_gate_note_sensor(startup_gate_t *s, uint32_t now, bool valid, bool clear)
{
    s->sensor_at = now; s->sensor_valid = valid; s->distance_clear = clear;
}
static inline void startup_gate_note_driver(startup_gate_t *s, uint32_t now, bool valid)
{
    s->driver_at = now; s->driver_valid = valid;
}
static inline void startup_gate_tick(startup_gate_t *s, uint32_t now)
{
    bool link = startup_gate_link_ready(s, now);
    bool profile_valid = s->profile == STARTUP_COMPUTER_BENCH || s->profile == STARTUP_VEHICLE_EXTERNAL_POWER;
    bool gimbal_ok = profile_valid && link && !s->fault && s->servo_power_verified;
    bool vehicle_ok = s->profile == STARTUP_VEHICLE_EXTERNAL_POWER && link && !s->fault &&
        s->vehicle_power_verified && s->sensor_valid && s->distance_clear && s->driver_valid &&
        (uint32_t)(now - s->sensor_at) <= STARTUP_SENSOR_MAX_AGE_MS &&
        (uint32_t)(now - s->driver_at) <= STARTUP_DRIVER_MAX_AGE_MS;
    if (!gimbal_ok) s->request_gimbal = false;
    if (!vehicle_ok) s->request_vehicle = false;
    if (s->link_messages && (uint32_t)(now - s->link_at) > STARTUP_LINK_MAX_AGE_MS) s->link_messages = 0;
    s->permit_gimbal = gimbal_ok && s->request_gimbal;
    s->permit_vehicle = vehicle_ok && s->request_vehicle;
    s->stage = s->fault ? STARTUP_FAULT : s->permit_vehicle ? STARTUP_VEHICLE_READY :
        s->permit_gimbal ? STARTUP_GIMBAL_READY : link ? STARTUP_LINK_READY : STARTUP_SAFE_IDLE;
}
static inline bool startup_gate_request_gimbal(startup_gate_t *s, uint32_t now)
{
    s->request_gimbal = true; startup_gate_tick(s, now); return s->permit_gimbal;
}
static inline bool startup_gate_request_vehicle(startup_gate_t *s, uint32_t now)
{
    s->request_vehicle = true; startup_gate_tick(s, now); return s->permit_vehicle;
}
static inline void startup_gate_stop(startup_gate_t *s, uint32_t now)
{
    s->request_gimbal = s->request_vehicle = false; startup_gate_tick(s, now);
}
static inline void startup_gate_fault(startup_gate_t *s, uint32_t now)
{
    s->fault = true; startup_gate_tick(s, now);
}
#endif
