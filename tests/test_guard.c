#include "app.h"
#include "adaptive.h"
#include "fusion.h"
#include "contact.h"
#include "trace.h"

#ifdef NDEBUG
#error Tests require assertions; do not define NDEBUG.
#endif

#include <assert.h>
#include <stdio.h>

static guard_t fresh_guard(uint32_t now_ms)
{
    guard_t guard;
    guard_config_t config = guard_default_config();
    assert(guard_init(&guard, &config, now_ms));
    return guard;
}

static void recover(guard_t *guard, uint32_t start_ms, uint16_t distance_mm)
{
    guard_update(guard, start_ms, true, true, distance_mm);
    assert(guard->state == GUARD_FAULT);
    guard_update(guard, start_ms + 50u, true, true, distance_mm);
    assert(guard->state == GUARD_FAULT);
    guard_update(guard, start_ms + 100u, true, true, distance_mm);
}

static void test_configuration(void)
{
    guard_t guard;
    guard_config_t config = guard_default_config();
    assert(!guard_init(NULL, &config, 0u));
    assert(!guard_init(&guard, NULL, 0u));
    config.danger_off_mm = config.danger_on_mm;
    assert(!guard_init(&guard, &config, 0u));
    config = guard_default_config();
    config.recovery_samples = 0u;
    assert(!guard_init(&guard, &config, 0u));
}

static void test_hysteresis_and_danger(void)
{
    guard_t guard = fresh_guard(0u);
    assert(guard.state == GUARD_FAULT);
    assert(guard.fault == GUARD_FAULT_NO_DATA);
    assert(!guard_output(&guard, 0u).motion_allowed);
    recover(&guard, 0u, 800u);
    assert(guard.state == GUARD_NORMAL);
    assert(guard_output(&guard, 100u).green_led);

    guard_update(&guard, 150u, true, true, 600u);
    assert(guard.state == GUARD_CAUTION);
    guard_update(&guard, 200u, true, true, 650u);
    assert(guard.state == GUARD_CAUTION);
    guard_update(&guard, 250u, true, true, 700u);
    assert(guard.state == GUARD_NORMAL);

    guard_update(&guard, 300u, true, true, 250u);
    assert(guard.state == GUARD_DANGER);
    assert(!guard_output(&guard, 300u).motion_allowed);
    guard_update(&guard, 350u, true, true, 319u);
    assert(guard.state == GUARD_DANGER);
    guard_update(&guard, 400u, true, true, 650u);
    assert(guard.state == GUARD_CAUTION);
}

static void test_bad_sample_and_recovery(void)
{
    guard_t guard = fresh_guard(0u);
    recover(&guard, 0u, 800u);
    guard_update(&guard, 150u, true, false, 0u);
    assert(guard.state == GUARD_FAULT);
    assert(guard.fault == GUARD_FAULT_BAD_SAMPLE);
    assert(!guard_output(&guard, 150u).motion_allowed);
    guard_update(&guard, 175u, true, true, 800u);
    guard_update(&guard, 180u, true, false, 0u);
    assert(guard.recovery_count == 0u);
    recover(&guard, 200u, 200u);
    assert(guard.state == GUARD_DANGER);
    assert(guard.fault == GUARD_FAULT_NONE);
}

typedef struct {
    uint32_t now_ms;
    app_sample_t sample;
    guard_output_t output;
    unsigned write_count;
    uint32_t read_advance_ms;
} fake_port_t;

static uint32_t fake_millis(void *context)
{
    return ((fake_port_t *)context)->now_ms;
}

static app_sample_t fake_sensor(void *context)
{
    fake_port_t *port = (fake_port_t *)context;
    port->now_ms += port->read_advance_ms;
    return port->sample;
}

static void fake_output(void *context, guard_output_t output)
{
    fake_port_t *port = (fake_port_t *)context;
    port->output = output;
    ++port->write_count;
}

static void test_application_loop(void)
{
    app_t app;
    fake_port_t port = {0};
    guard_config_t config = guard_default_config();
    app_ports_t ports = {fake_millis, fake_sensor, fake_output};
    assert(!app_init(&app, NULL, &port, &config));
    assert(app_init(&app, &ports, &port, &config));
    port.sample = (app_sample_t){true, true, 800u};
    app_tick(&app);
    port.now_ms = 50u;
    app_tick(&app);
    port.now_ms = 100u;
    app_tick(&app);
    assert(app.guard.state == GUARD_NORMAL);
    assert(port.output.green_led && port.output.motion_allowed);
    port.now_ms = 150u;
    port.sample = (app_sample_t){true, false, 0u};
    app_tick(&app);
    assert(app.guard.state == GUARD_FAULT);
    assert(!port.output.motion_allowed);
    assert(port.write_count == 4u);
}

static void test_sample_read_crosses_timeout(void)
{
    app_t app;
    fake_port_t port = {0};
    guard_config_t config = guard_default_config();
    app_ports_t ports = {fake_millis, fake_sensor, fake_output};
    assert(app_init(&app, &ports, &port, &config));
    port.sample = (app_sample_t){true, true, 800u};
    app_tick(&app);
    port.now_ms = 50u;
    app_tick(&app);
    port.now_ms = 100u;
    app_tick(&app);
    assert(port.output.motion_allowed);
    port.now_ms = 399u;
    port.read_advance_ms = 1u;
    port.sample = (app_sample_t){false, false, 0u};
    app_tick(&app);
    assert(port.now_ms == 400u);
    assert(app.guard.state == GUARD_FAULT);
    assert(app.guard.fault == GUARD_FAULT_STALE);
    assert(!port.output.motion_allowed);
}

static void test_optional_bumper_fusion(void)
{
    guard_t guard = fresh_guard(0u);
    fusion_result_t result = fusion_decide(&guard, false, 0u);
    fusion_result_t missing_guard = fusion_decide(NULL, false, 0u);
    assert(missing_guard.state == GUARD_FAULT);
    assert(missing_guard.output.red_led && !missing_guard.output.motion_allowed);
    assert(result.state == GUARD_FAULT);
    assert(result.reasons == FUSION_REASON_DISTANCE_FAULT);
    assert(!result.output.motion_allowed);
    recover(&guard, 0u, 800u);

    result = fusion_decide(&guard, false, 100u);
    assert(result.state == GUARD_NORMAL);
    assert(result.reasons == FUSION_REASON_NONE);
    assert(result.output.motion_allowed);
    result = fusion_decide(&guard, true, 100u);
    assert(result.state == GUARD_DANGER);
    assert(result.reasons == FUSION_REASON_CONTACT);
    assert(!result.output.motion_allowed);

    guard_update(&guard, 150u, true, false, 0u);
    result = fusion_decide(&guard, true, 150u);
    assert(result.state == GUARD_FAULT);
    assert(result.reasons == (FUSION_REASON_CONTACT |
                              FUSION_REASON_DISTANCE_FAULT));
    assert(!result.output.motion_allowed);
}

static void test_optional_adaptive_threshold(void)
{
    const adaptive_point_t points[] = {
        {0u, 0u}, {100u, 20u}, {500u, 400u}
    };
    const adaptive_point_t bad_points[] = {
        {100u, 20u}, {100u, 30u}
    };
    uint16_t trigger = 0u;
    assert(adaptive_trigger_distance(0u, points, 3u, 100u, 100u,
                                     250u, &trigger));
    assert(trigger == 250u);
    assert(adaptive_trigger_distance(400u, points, 3u, 100u, 100u,
                                     250u, &trigger));
    assert(trigger == 540u);
    assert(!adaptive_trigger_distance(501u, points, 3u, 100u, 100u,
                                      250u, &trigger));
    assert(!adaptive_trigger_distance(50u, bad_points, 2u, 100u, 100u,
                                      250u, &trigger));
    assert(!adaptive_trigger_distance(50u, points, 3u, 100u, 100u,
                                      250u, NULL));
}

static void test_stale_and_clock_wrap(void)
{
    guard_t guard = fresh_guard(0u);
    recover(&guard, 0u, 800u);
    guard_update(&guard, 399u, false, false, 0u);
    assert(guard.state == GUARD_NORMAL);
    guard_update(&guard, 400u, false, false, 0u);
    assert(guard.state == GUARD_FAULT);
    assert(guard.fault == GUARD_FAULT_STALE);
    recover(&guard, 450u, 800u);
    assert(guard.state == GUARD_NORMAL);

    guard = fresh_guard(UINT32_MAX - 50u);
    guard_update(&guard, UINT32_MAX - 50u, true, true, 800u);
    guard_update(&guard, UINT32_MAX, true, true, 800u);
    guard_update(&guard, 49u, true, true, 800u);
    assert(guard.state == GUARD_NORMAL);
    guard_update(&guard, 348u, false, false, 0u);
    assert(guard.state == GUARD_NORMAL);
    guard_update(&guard, 349u, false, false, 0u);
    assert(guard.state == GUARD_FAULT);
}

static void test_output_patterns(void)
{
    guard_t guard = fresh_guard(0u);
    guard_output_t output = guard_output(&guard, 0u);
    assert(output.red_led && output.buzzer && !output.motion_allowed);
    output = guard_output(&guard, 300u);
    assert(!output.red_led && !output.buzzer);
    recover(&guard, 0u, 200u);
    output = guard_output(&guard, 100u);
    assert(output.red_led && output.buzzer && !output.motion_allowed);
    output = guard_output(&guard, 300u);
    assert(output.red_led && !output.buzzer);
}

static void test_stale_output_without_update(void)
{
    guard_t guard = fresh_guard(0u);
    fusion_result_t result;
    recover(&guard, 0u, 800u);
    assert(guard_output(&guard, 399u).motion_allowed);
    assert(!guard_output(&guard, 400u).motion_allowed);
    result = fusion_decide(&guard, false, 400u);
    assert(result.state == GUARD_FAULT);
    assert(result.reasons == FUSION_REASON_DISTANCE_FAULT);
    assert(!result.output.motion_allowed);
    result = fusion_decide(&guard, true, 400u);
    assert(result.state == GUARD_FAULT);
    assert(result.reasons == (FUSION_REASON_DISTANCE_FAULT | FUSION_REASON_CONTACT));
}

static void test_contact_release_filter(void)
{
    contact_t contact;
    contact_init(&contact);
    assert(contact.active);
    assert(contact_update(&contact, false, 0u, 30u));
    assert(contact_update(&contact, false, 29u, 30u));
    assert(!contact_update(&contact, false, 30u, 30u));
    assert(contact_update(&contact, true, 31u, 30u));
    assert(contact_update(&contact, false, 32u, 30u));
    assert(contact_update(&contact, true, 40u, 30u));
    assert(contact_update(&contact, false, 50u, 30u));
    assert(contact_update(&contact, false, 79u, 30u));
    assert(!contact_update(&contact, false, 80u, 30u));
    assert(contact_update(&contact, true, UINT32_MAX - 10u, 30u));
    assert(contact_update(&contact, false, UINT32_MAX - 9u, 30u));
    assert(contact_update(&contact, false, 19u, 30u));
    assert(!contact_update(&contact, false, 20u, 30u));
    assert(contact_update(NULL, false, 0u, 30u));
}

static void test_strict_trace_parser(void)
{
    trace_row_t row = {17u, false, false, 19u};
    const char *bad[] = {
        "", "0,1,1", "-1,1,1,800", "+1,1,1,800",
        "4294967296,1,1,800", "0,2,1,800", "0,1,2,800",
        "0,1,1,65536", "0,1,1,999999999999999999999",
        "0,1,1,800,1", "0,1,1,800junk", "0,,1,800",
        "0,1,1,800\n1,1,1,800"
    };
    size_t i;
    for (i = 0u; i < sizeof bad / sizeof bad[0]; ++i) {
        assert(!trace_parse_row(bad[i], &row));
        assert(row.time_ms == 17u && row.distance_mm == 19u);
    }
    assert(!trace_parse_row(NULL, &row));
    assert(!trace_parse_row("0,1,1,1", NULL));
    assert(trace_parse_row(" 4294967295 , 1 , 0 , 65535 \r\n", &row));
    assert(row.time_ms == UINT32_MAX && row.available && !row.valid);
    assert(row.distance_mm == UINT16_MAX);
    assert(trace_parse_row("0,0,0,0", &row));
    assert(row.time_ms == 0u && !row.available && !row.valid && row.distance_mm == 0u);
}

static void test_adaptive_numeric_boundaries(void)
{
    const adaptive_point_t small[] = {{1u, 0u}};
    const adaptive_point_t huge[] = {{65535u, 65535u}};
    const adaptive_point_t decreasing[] = {{1u, 20u}, {2u, 19u}};
    uint16_t result = 42u;
    assert(adaptive_trigger_distance(1u, small, 1u, 1u, 1u, 1u, &result));
    assert(result == 2u); /* Fractional travel rounds up. */
    result = 42u;
    assert(!adaptive_trigger_distance(65535u, huge, 1u, 65535u, 65535u, 1u, &result));
    assert(result == 42u);
    assert(!adaptive_trigger_distance(1u, decreasing, 2u, 1u, 1u, 1u, &result));
    assert(result == 42u);
}

int main(void)
{
    test_configuration();
    test_hysteresis_and_danger();
    test_bad_sample_and_recovery();
    test_stale_and_clock_wrap();
    test_output_patterns();
    test_application_loop();
    test_sample_read_crosses_timeout();
    test_optional_bumper_fusion();
    test_optional_adaptive_threshold();
    test_stale_output_without_update();
    test_contact_release_filter();
    test_strict_trace_parser();
    test_adaptive_numeric_boundaries();
    puts("all 13 software test groups passed");
    return 0;
}
