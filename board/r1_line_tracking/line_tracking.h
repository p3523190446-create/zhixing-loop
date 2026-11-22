#ifndef LINE_TRACKING_H
#define LINE_TRACKING_H
#include <stdint.h>
void line_tracking_init(uint32_t now);
void line_tracking_poll(uint32_t now);
int line_tracking_command(const char *command,uint32_t now,void (*reply)(const char *));
#endif
