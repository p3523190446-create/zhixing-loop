#include "contact.h"
#include <stddef.h>
void contact_init(contact_t *contact)
{
    if (contact == NULL) { return; }
    contact->active = true;
    contact->release_pending = false;
    contact->released_since_ms = 0u;
}

bool contact_update(contact_t *contact, bool raw_pressed,
                    uint32_t now_ms, uint16_t release_ms)
{
    if (contact == NULL) { return true; }
    if (raw_pressed) {
        contact->active = true;
        contact->release_pending = false;
    } else if (contact->active) {
        if (!contact->release_pending) {
            contact->release_pending = true;
            contact->released_since_ms = now_ms;
        }
        if ((uint32_t)(now_ms - contact->released_since_ms) >= release_ms) {
            contact->active = false;
            contact->release_pending = false;
        }
    }
    return contact->active;
}
