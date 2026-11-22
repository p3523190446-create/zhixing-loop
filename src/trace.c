#include "trace.h"
#include <stddef.h>

static void skip_spaces(const char **cursor)
{
    while (**cursor == ' ' || **cursor == '\t') { ++*cursor; }
}

static bool read_number(const char **cursor, uint32_t limit, uint32_t *value)
{
    uint32_t number = 0u;
    skip_spaces(cursor);
    if (**cursor < '0' || **cursor > '9') { return false; }
    while (**cursor >= '0' && **cursor <= '9') {
        uint32_t digit = (uint32_t)(**cursor - '0');
        if (digit > limit || number > (limit - digit) / 10u) {
            return false;
        }
        number = number * 10u + digit;
        ++*cursor;
    }
    skip_spaces(cursor);
    *value = number;
    return true;
}

bool trace_parse_row(const char *line, trace_row_t *row)
{
    uint32_t values[4];
    const uint32_t limits[4] = {UINT32_MAX, 1u, 1u, UINT16_MAX};
    unsigned i;
    const char *cursor = line;
    if (line == NULL || row == NULL) { return false; }
    for (i = 0u; i < 4u; ++i) {
        if (!read_number(&cursor, limits[i], &values[i])) { return false; }
        if (i < 3u && *cursor++ != ',') { return false; }
    }
    if (*cursor == '\r') { ++cursor; }
    if (*cursor == '\n') { ++cursor; }
    if (*cursor != '\0') { return false; }
    row->time_ms = values[0];
    row->available = values[1] != 0u;
    row->valid = values[2] != 0u;
    row->distance_mm = (uint16_t)values[3];
    return true;
}
