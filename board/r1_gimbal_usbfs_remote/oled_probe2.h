#ifndef ZXR_OLED_PROBE2_H
#define ZXR_OLED_PROBE2_H
#include <stdint.h>
void oled_probe2_init(void);
void oled_probe2_poll(uint32_t now);
uint8_t oled2_bus_write(uint8_t address,uint8_t control,const uint8_t *bytes,unsigned count);
extern volatile uint32_t oled2_scan_count, oled2_ack_3c, oled2_ack_3d, oled2_bus_error, oled2_idle_lines;
#endif
