#ifndef ZHIXING_FUSION_H
#define ZHIXING_FUSION_H

#include "guard.h"

/* Optional plan B. The bumper signal must already be debounced by its driver. */
enum {
    FUSION_REASON_NONE = 0u,
    FUSION_REASON_CONTACT = 1u,
    FUSION_REASON_DISTANCE_FAULT = 2u
};

typedef struct {
    guard_state_t state;
    unsigned reasons;
    guard_output_t output;
} fusion_result_t;

fusion_result_t fusion_decide(const guard_t *distance_guard,
                              bool bumper_pressed, uint32_t now_ms);

#endif
