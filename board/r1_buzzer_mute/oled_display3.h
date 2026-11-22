#ifndef ZXR_OLED_DISPLAY3_H
#define ZXR_OLED_DISPLAY3_H
#include <stdint.h>
void oled_display3_poll(uint32_t now);
extern volatile uint32_t oled_display3_ready, oled_display3_frames, oled_display3_errors;
#endif
