#ifndef ZHIXING_APP_H
#define ZHIXING_APP_H

#include "guard.h"

typedef struct {
    bool available;
    bool valid;
    uint16_t distance_mm;
} app_sample_t;

typedef struct {
    uint32_t (*millis)(void *context);
    /* Must return promptly; no long busy wait for a sensor conversion. */
    app_sample_t (*read_sensor)(void *context);
    void (*write_output)(void *context, guard_output_t output);
} app_ports_t;

typedef struct {
    guard_t guard;
    app_ports_t ports;
    void *context;
} app_t;

bool app_init(app_t *app, const app_ports_t *ports, void *context,
              const guard_config_t *config);
/* Call only after app_init() has returned true. */
void app_tick(app_t *app);

#endif
