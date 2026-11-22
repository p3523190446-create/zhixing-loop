#ifndef ZHIXING_CONTACT_H
#define ZHIXING_CONTACT_H
#include <stdbool.h>
#include <stdint.h>
typedef struct {
    bool active;
    bool release_pending;
    uint32_t released_since_ms;
} contact_t;
/* Starts active until a continuously released input has been observed. */
void contact_init(contact_t *contact);
/* Press immediately; release only after release_ms without another press. */
bool contact_update(contact_t *contact, bool raw_pressed,
                    uint32_t now_ms, uint16_t release_ms);
#endif
