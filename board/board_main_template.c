/*
 * CH32V307 integration template, not a finished board driver.
 * Implement the board_* functions with the actual board schematic, sensor
 * datasheet, official BSP and MounRiver Studio project before linking.
 */
#include "app.h"

extern void board_init(void);
extern uint32_t board_millis(void);
extern app_sample_t board_poll_distance(void);
extern void board_write_outputs(guard_output_t output);
extern void board_delay_ms(uint32_t delay_ms);

static uint32_t port_millis(void *context)
{
    (void)context;
    return board_millis();
}

static app_sample_t port_read_sensor(void *context)
{
    (void)context;
    return board_poll_distance();
}

static void port_write_output(void *context, guard_output_t output)
{
    (void)context;
    board_write_outputs(output);
}

int main(void)
{
    app_t app;
    guard_config_t config = guard_default_config();
    const app_ports_t ports = {
        port_millis, port_read_sensor, port_write_output
    };

    board_init();
    if (!app_init(&app, &ports, 0, &config)) {
        for (;;) {
            /* A configuration error must not silently permit motion. */
            board_write_outputs((guard_output_t){0, 0, 1, 1, 0});
            board_delay_ms(100u);
        }
    }

    for (;;) {
        app_tick(&app);
        board_delay_ms(10u);
    }
}
