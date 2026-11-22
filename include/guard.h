#ifndef ZHIXING_GUARD_H
#define ZHIXING_GUARD_H

#include <stdbool.h>
#include <stdint.h>

/* All distances are millimetres. Time is a wrapping 32-bit millisecond clock. */
typedef enum {
    GUARD_NORMAL,
    GUARD_CAUTION,
    GUARD_DANGER,
    GUARD_FAULT
} guard_state_t;

typedef enum {
    GUARD_FAULT_NONE,
    GUARD_FAULT_NO_DATA,
    GUARD_FAULT_BAD_SAMPLE,
    GUARD_FAULT_STALE
} guard_fault_t;

typedef struct {
    uint16_t danger_on_mm;
    uint16_t danger_off_mm;
    uint16_t caution_on_mm;
    uint16_t caution_off_mm;
    uint32_t sample_timeout_ms;
    uint8_t recovery_samples;
} guard_config_t;

typedef struct {
    guard_config_t config;
    guard_state_t state;
    guard_fault_t fault;
    uint32_t last_good_ms;
    uint16_t last_distance_mm;
    uint8_t recovery_count;
} guard_t;

typedef struct {
    bool green_led;
    bool yellow_led;
    bool red_led;
    bool buzzer;
    /* Logical permission only. No motor is connected by this library. */
    bool motion_allowed;
} guard_output_t;

guard_config_t guard_default_config(void);
bool guard_init(guard_t *guard, const guard_config_t *config, uint32_t now_ms);

/*
 * Call on a regular schedule and whenever a new sensor result arrives.
 * has_sample=false: no new result yet; valid and distance_mm are ignored.
 * has_sample=true, valid=false: sensor driver reports timeout/error/invalid data.
 * The driver must determine validity from the chosen sensor's specification.
 */
void guard_update(guard_t *guard, uint32_t now_ms, bool has_sample,
                  bool valid, uint16_t distance_mm);

/* Non-blocking LED/buzzer patterns; call repeatedly with the current time. */
guard_output_t guard_output(const guard_t *guard, uint32_t now_ms);

const char *guard_state_name(guard_state_t state);
const char *guard_fault_name(guard_fault_t fault);

#endif
