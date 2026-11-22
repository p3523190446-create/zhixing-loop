#ifndef ZHIXING_ADAPTIVE_H
#define ZHIXING_ADAPTIVE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Optional plan C. Stop distance should be the largest observed in repeated
 * real tests under the documented load, power and surface conditions. */
typedef struct {
    uint16_t speed_mm_s;
    uint16_t measured_stop_mm;
} adaptive_point_t;

/*
 * Uses the next calibrated speed (conservative step lookup), then adds the
 * distance travelled during measured response latency and a fixed margin.
 * Returns false for invalid calibration or speeds above the tested range.
 */
bool adaptive_trigger_distance(uint16_t speed_mm_s,
                               const adaptive_point_t *points,
                               size_t point_count,
                               uint16_t response_ms,
                               uint16_t margin_mm,
                               uint16_t minimum_mm,
                               uint16_t *trigger_mm);

#endif
