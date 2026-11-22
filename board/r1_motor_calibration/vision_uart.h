#ifndef VISION_UART_H
#define VISION_UART_H
#include <stdint.h>
void vision_uart_init(void);
void vision_uart_poll(uint32_t now_ms);
extern volatile uint32_t vision_valid, vision_seq, vision_class;
extern volatile uint32_t vision_score, vision_cx, vision_cy, vision_last_ms;
extern volatile uint32_t vision_accepted, vision_rejected, vision_rx_errors;
#endif
