#ifndef ZXR_OLED_PROBE3_H
#define ZXR_OLED_PROBE3_H
#include <stdint.h>
void oled_probe3_init(void);
void oled_probe3_poll(uint32_t now);
uint8_t oled3_bus_write(uint8_t address,uint8_t control,const uint8_t *bytes,unsigned count);
extern volatile uint32_t oled3_scan_count, oled3_ack_3c, oled3_ack_3d, oled3_bus_error, oled3_idle_lines;
#endif
