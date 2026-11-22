#ifndef SETTINGS_H
#define SETTINGS_H
#include <stdint.h>
#define SETTINGS_BASE 0x7FE000u
extern volatile uint32_t settings_ready,settings_busy,settings_saved_mm,settings_sequence,settings_saved_muted;
extern volatile uint32_t settings_ui_active,settings_ui_status,settings_ui_ms,settings_error,settings_saves,settings_loaded;
void settings_init(uint32_t now);
void settings_poll(uint32_t now);
void settings_request(uint16_t mm,uint8_t muted,uint32_t now);
int settings_debug_read(uint32_t offset,uint8_t *out);
#endif
