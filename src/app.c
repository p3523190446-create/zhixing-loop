#include "app.h"

#include <stddef.h>

bool app_init(app_t *app, const app_ports_t *ports, void *context,
              const guard_config_t *config)
{
    if (app == NULL || ports == NULL || ports->millis == NULL ||
        ports->read_sensor == NULL || ports->write_output == NULL ||
        config == NULL) {
        return false;
    }
    app->ports = *ports;
    app->context = context;
    return guard_init(&app->guard, config, ports->millis(context));
}

void app_tick(app_t *app)
{
    uint32_t now_ms;
    app_sample_t sample;
    if (app == NULL) {
        return;
    }
    sample = app->ports.read_sensor(app->context);
    /* Even a bounded bus read can cross the stale-data boundary. */
    now_ms = app->ports.millis(app->context);
    guard_update(&app->guard, now_ms, sample.available, sample.valid,
                 sample.distance_mm);
    app->ports.write_output(app->context, guard_output(&app->guard, now_ms));
}
