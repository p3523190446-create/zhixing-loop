#include "adaptive.h"

#include <stdint.h>

bool adaptive_trigger_distance(uint16_t speed_mm_s,
                               const adaptive_point_t *points,
                               size_t point_count,
                               uint16_t response_ms,
                               uint16_t margin_mm,
                               uint16_t minimum_mm,
                               uint16_t *trigger_mm)
{
    size_t i;
    uint64_t distance;
    if (points == NULL || point_count == 0u || trigger_mm == NULL ||
        minimum_mm == 0u) {
        return false;
    }
    for (i = 1u; i < point_count; ++i) {
        if (points[i].speed_mm_s <= points[i - 1u].speed_mm_s ||
            points[i].measured_stop_mm < points[i - 1u].measured_stop_mm) {
            return false;
        }
    }
    for (i = 0u; i < point_count; ++i) {
        if (speed_mm_s <= points[i].speed_mm_s) {
            break;
        }
    }
    if (i == point_count) {
        return false;
    }
    distance = (uint64_t)points[i].measured_stop_mm +
               ((uint64_t)speed_mm_s * response_ms + 999u) / 1000u +
               margin_mm;
    if (distance < minimum_mm) {
        distance = minimum_mm;
    }
    if (distance > UINT16_MAX) {
        return false;
    }
    *trigger_mm = (uint16_t)distance;
    return true;
}
