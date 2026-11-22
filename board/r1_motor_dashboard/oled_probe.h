#ifndef ZXR_OLED_PROBE_H
#define ZXR_OLED_PROBE_H
#include <stdint.h>
void oled_probe_init(void);
void oled_probe_poll(uint32_t now);
uint8_t oled_bus_write(uint8_t address,uint8_t control,const uint8_t *bytes,unsigned count);
extern volatile uint32_t oled_scan_count, oled_ack_3c, oled_ack_3d, oled_bus_error, oled_idle_lines;
#endif
