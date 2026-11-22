#ifndef ZXR_OLED_DISPLAY2_H
#define ZXR_OLED_DISPLAY2_H
#include <stdint.h>
void oled_display2_poll(uint32_t now);
extern volatile uint32_t oled_display2_ready, oled_display2_frames, oled_display2_errors;
#endif
