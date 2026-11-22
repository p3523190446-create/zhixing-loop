#ifndef UVC_BRIDGE_H
#define UVC_BRIDGE_H
#include <stdint.h>
void uvc_bridge_poll(uint32_t now);
void uvc_bridge_stop(void);
int uvc_bridge_command(const char *text,uint32_t now,void (*send)(const char *));
#endif
