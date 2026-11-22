#include "app.h"

#include <stdio.h>

typedef struct {
    uint32_t now_ms;
    app_sample_t sample;
    guard_output_t output;
} fake_board_t;

static uint32_t fake_millis(void *context)
{
    return ((fake_board_t *)context)->now_ms;
}

static app_sample_t fake_read_sensor(void *context)
{
    return ((fake_board_t *)context)->sample;
}

static void fake_write_output(void *context, guard_output_t output)
{
    ((fake_board_t *)context)->output = output;
}

static void step(app_t *app, fake_board_t *board, uint32_t now_ms,
                 bool available, bool valid, uint16_t distance_mm)
{
    board->now_ms = now_ms;
    board->sample = (app_sample_t){available, valid, distance_mm};
    app_tick(app);
    printf("%4lu ms  %4u mm  %-7s fault=%-10s G=%u Y=%u R=%u B=%u\n",
           (unsigned long)now_ms, (unsigned)distance_mm,
           guard_state_name(app->guard.state),
           guard_fault_name(app->guard.fault),
           (unsigned)board->output.green_led, (unsigned)board->output.yellow_led,
           (unsigned)board->output.red_led, (unsigned)board->output.buzzer);
}

int main(void)
{
    app_t app;
    fake_board_t board = {0};
    guard_config_t config = guard_default_config();
    app_ports_t ports = {fake_millis, fake_read_sensor, fake_write_output};
    if (!app_init(&app, &ports, &board, &config)) {
        return 1;
    }

    puts("Desktop simulation only; no real sensor or CH32V307 board is used.");
    step(&app, &board, 0u, true, true, 900u);
    step(&app, &board, 50u, true, true, 900u);
    step(&app, &board, 100u, true, true, 900u);
    step(&app, &board, 150u, true, true, 550u);
    step(&app, &board, 200u, true, true, 200u);
    step(&app, &board, 250u, true, false, 0u);
    step(&app, &board, 300u, true, true, 800u);
    step(&app, &board, 350u, true, true, 800u);
    step(&app, &board, 400u, true, true, 800u);
    step(&app, &board, 750u, false, false, 0u);
    return 0;
}
