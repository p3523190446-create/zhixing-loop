#include "guard.h"
#include "trace.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* Preserve real bytes; embedded NUL must never hide a damaged row suffix. */
static int read_trace_line(FILE *stream, char *line, size_t capacity)
{
    size_t count = 0u;
    int byte;
    while ((byte = fgetc(stream)) != EOF) {
        if (byte == 0 || count + 1u >= capacity) { return -1; }
        line[count++] = (char)byte;
        if (byte == '\n') { break; }
    }
    if (ferror(stream)) { return -1; }
    line[count] = '\0';
    return count == 0u ? 0 : 1;
}

/* Replay recorded inputs without claiming they came from actual hardware. */
int main(int argc, char **argv)
{
    FILE *stream;
    char line[160];
    unsigned line_number = 0u;
    uint32_t last_time = 0u;
    bool initialized = false;
    int read_status;
    guard_t guard;
    guard_config_t config = guard_default_config();

    if (argc != 2) {
        fputs("usage: guard_replay trace.csv\n", stderr);
        return 2;
    }
    stream = fopen(argv[1], "rb");
    if (stream == NULL) {
        perror(argv[1]);
        return 2;
    }
    puts("time_ms,state,fault,green,yellow,red,buzzer,motion_allowed");
    while ((read_status = read_trace_line(stream, line, sizeof line)) > 0) {
        trace_row_t row;
        char *data = line;
        guard_output_t output;
        uint32_t now_ms;
        ++line_number;
        if (line_number == 1u && strlen(line) >= 3u &&
            (unsigned char)line[0] == 0xEFu &&
            (unsigned char)line[1] == 0xBBu &&
            (unsigned char)line[2] == 0xBFu) { data += 3; }
        while (*data == ' ' || *data == '\t') { ++data; }
        if (*data == '#' || *data == '\0' || strcmp(data, "\n") == 0 ||
            strcmp(data, "\r\n") == 0 || strcmp(data, "\r") == 0) {
            continue;
        }
        if (!trace_parse_row(data, &row)) {
            fprintf(stderr, "invalid row at line %u\n", line_number);
            fclose(stream);
            return 2;
        }
        now_ms = row.time_ms;
        if (initialized && now_ms <= last_time) {
            fprintf(stderr, "time must increase at line %u\n", line_number);
            fclose(stream);
            return 2;
        }
        if (!initialized) {
            if (!guard_init(&guard, &config, now_ms)) {
                fclose(stream);
                return 2;
            }
            initialized = true;
        }
        guard_update(&guard, now_ms, row.available, row.valid, row.distance_mm);
        output = guard_output(&guard, now_ms);
        printf("%lu,%s,%s,%u,%u,%u,%u,%u\n", (unsigned long)now_ms,
               guard_state_name(guard.state), guard_fault_name(guard.fault),
               (unsigned)output.green_led, (unsigned)output.yellow_led,
               (unsigned)output.red_led, (unsigned)output.buzzer,
               (unsigned)output.motion_allowed);
        last_time = now_ms;
    }
    if (read_status < 0) {
        fprintf(stderr, "invalid bytes, long line or read error at line %u\n", line_number + 1u);
        fclose(stream);
        return 2;
    }
    if (!initialized) {
        fputs("empty or unreadable trace\n", stderr);
        fclose(stream);
        return 2;
    }
    fclose(stream);
    return 0;
}
