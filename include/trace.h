#ifndef ZHIXING_TRACE_H
#define ZHIXING_TRACE_H
#include <stdbool.h>
#include <stdint.h>
typedef struct {
    uint32_t time_ms;
    bool available;
    bool valid;
    uint16_t distance_mm;
} trace_row_t;
/* Strict unsigned decimal fields; rejects overflow, signs and trailing data. */
bool trace_parse_row(const char *line, trace_row_t *row);
#endif
