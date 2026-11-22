#ifndef ZXR_OLED_DISPLAY_H
#define ZXR_OLED_DISPLAY_H
#include <stdint.h>
void oled_display_poll(uint32_t now);
extern volatile uint32_t oled_display_ready, oled_display_frames, oled_display_errors;
#endif
