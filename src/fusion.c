#include "fusion.h"

#include <stddef.h>

fusion_result_t fusion_decide(const guard_t *distance_guard,
                              bool bumper_pressed, uint32_t now_ms)
{
    fusion_result_t result;
    guard_t output_guard;
    guard_t fallback_guard = {0};
    result.state = GUARD_FAULT;
    result.reasons = FUSION_REASON_DISTANCE_FAULT;
    fallback_guard.state = GUARD_FAULT;
    result.output = guard_output(&fallback_guard, now_ms);
    if (distance_guard == NULL) {
        return result;
    }

    output_guard = *distance_guard;
    result.state = distance_guard->state;
    result.reasons = FUSION_REASON_NONE;
    if (distance_guard->state == GUARD_FAULT ||
        (uint32_t)(now_ms - distance_guard->last_good_ms) >=
        distance_guard->config.sample_timeout_ms) {
        result.state = GUARD_FAULT;
        result.reasons |= FUSION_REASON_DISTANCE_FAULT;
    }
    if (bumper_pressed) {
        result.reasons |= FUSION_REASON_CONTACT;
        if (result.state != GUARD_FAULT) {
            result.state = GUARD_DANGER;
        }
    }
    output_guard.state = result.state;
    result.output = guard_output(&output_guard, now_ms);
    return result;
}
