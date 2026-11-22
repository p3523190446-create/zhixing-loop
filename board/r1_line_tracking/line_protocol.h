#ifndef LINE_PROTOCOL_H
#define LINE_PROTOCOL_H
#include <stdint.h>
typedef struct {
    char frame[144];
    unsigned length;
    uint16_t analog[8];
    uint8_t digital[8];
    uint32_t analog_frames, digital_frames, rejected;
    uint32_t analog_ms, digital_ms;
} line_protocol_t;
void line_protocol_byte(line_protocol_t *p, uint8_t byte, uint32_t now);
void line_protocol_reset_frame(line_protocol_t *p);
int line_protocol_fresh(uint32_t frames, uint32_t last, uint32_t now);
#endif
