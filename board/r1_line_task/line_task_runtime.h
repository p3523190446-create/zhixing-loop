#ifndef ZX_LINE_TASK_RUNTIME_H
#define ZX_LINE_TASK_RUNTIME_H
#include <stdint.h>
void line_task_poll(uint32_t now);
int line_task_command(const char *text, uint32_t now, void (*reply)(const char *));
int line_task_usb_command(const char *text, uint32_t now, void (*reply)(const char *));
int line_task_running(void);
#endif
