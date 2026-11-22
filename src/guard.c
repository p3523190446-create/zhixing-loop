#include "guard.h"

#include <stddef.h>

guard_config_t guard_default_config(void)
{
    guard_config_t config = {250u, 320u, 600u, 700u, 300u, 3u};
    return config;
}

bool guard_init(guard_t *guard, const guard_config_t *config, uint32_t now_ms)
{
    if (guard == NULL || config == NULL || config->danger_on_mm == 0u ||
        config->danger_on_mm >= config->danger_off_mm ||
        config->danger_off_mm >= config->caution_on_mm ||
        config->caution_on_mm >= config->caution_off_mm ||
        config->sample_timeout_ms == 0u ||
        config->sample_timeout_ms >= UINT32_MAX / 2u ||
        config->recovery_samples == 0u) {
        return false;
    }

    guard->config = *config;
    guard->state = GUARD_FAULT;
    guard->fault = GUARD_FAULT_NO_DATA;
    guard->last_good_ms = now_ms;
    guard->last_distance_mm = 0u;
    guard->recovery_count = 0u;
    return true;
}

static guard_state_t classify(guard_state_t previous,
                              const guard_config_t *config,
                              uint16_t distance_mm)
{
    if (previous == GUARD_DANGER && distance_mm < config->danger_off_mm) {
        return GUARD_DANGER;
    }
    if (distance_mm <= config->danger_on_mm) {
        return GUARD_DANGER;
    }
    if ((previous == GUARD_CAUTION || previous == GUARD_DANGER) &&
        distance_mm < config->caution_off_mm) {
        return GUARD_CAUTION;
    }
    if (distance_mm <= config->caution_on_mm) {
        return GUARD_CAUTION;
    }
    return GUARD_NORMAL;
}

void guard_update(guard_t *guard, uint32_t now_ms, bool has_sample,
                  bool valid, uint16_t distance_mm)
{
    if (guard == NULL) {
        return;
    }

    /* Unsigned subtraction also works when the millisecond clock wraps. */
    if ((uint32_t)(now_ms - guard->last_good_ms) >=
        guard->config.sample_timeout_ms) {
        guard->state = GUARD_FAULT;
        guard->fault = GUARD_FAULT_STALE;
        guard->recovery_count = 0u;
    }

    if (!has_sample) {
        return;
    }
    if (!valid) {
        guard->state = GUARD_FAULT;
        guard->fault = GUARD_FAULT_BAD_SAMPLE;
        guard->recovery_count = 0u;
        return;
    }

    guard->last_good_ms = now_ms;
    guard->last_distance_mm = distance_mm;
    if (guard->state == GUARD_FAULT) {
        ++guard->recovery_count;
        if (guard->recovery_count < guard->config.recovery_samples) {
            return;
        }
        guard->recovery_count = 0u;
        guard->state = classify(GUARD_NORMAL, &guard->config, distance_mm);
    } else {
        guard->state = classify(guard->state, &guard->config, distance_mm);
    }
    guard->fault = GUARD_FAULT_NONE;
}

guard_output_t guard_output(const guard_t *guard, uint32_t now_ms)
{
    guard_output_t output = {false, false, false, false, false};
    guard_state_t effective_state;
    if (guard == NULL) {
        return output;
    }

    effective_state = guard->state;
    /* Do not publish a stale permission even if update() was skipped. */
    if ((uint32_t)(now_ms - guard->last_good_ms) >=
        guard->config.sample_timeout_ms) {
        effective_state = GUARD_FAULT;
    }
    switch (effective_state) {
    case GUARD_NORMAL:
        output.green_led = true;
        output.motion_allowed = true;
        break;
    case GUARD_CAUTION:
        output.yellow_led = true;
        output.motion_allowed = true;
        break;
    case GUARD_DANGER:
        output.red_led = true;
        output.buzzer = now_ms % 500u < 250u;
        break;
    case GUARD_FAULT:
    default:
        output.red_led = now_ms % 500u < 250u;
        output.buzzer = now_ms % 1000u < 100u;
        break;
    }
    return output;
}

const char *guard_state_name(guard_state_t state)
{
    switch (state) {
    case GUARD_NORMAL: return "NORMAL";
    case GUARD_CAUTION: return "CAUTION";
    case GUARD_DANGER: return "DANGER";
    case GUARD_FAULT: return "FAULT";
    default: return "UNKNOWN";
    }
}

const char *guard_fault_name(guard_fault_t fault)
{
    switch (fault) {
    case GUARD_FAULT_NONE: return "NONE";
    case GUARD_FAULT_NO_DATA: return "NO_DATA";
    case GUARD_FAULT_BAD_SAMPLE: return "BAD_SAMPLE";
    case GUARD_FAULT_STALE: return "STALE";
    default: return "UNKNOWN";
    }
}
