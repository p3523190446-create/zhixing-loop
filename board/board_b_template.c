/* Optional B integration. Choose this OR board_main_template.c, never both. */
#include "app.h"
#include "contact.h"
#include "fusion.h"

extern void board_init(void);
extern uint32_t board_millis(void);
extern app_sample_t board_poll_distance(void);
extern bool board_bumper_pressed(void); /* Map actual GPIO polarity here. */
extern void board_write_outputs(guard_output_t output);
extern void board_delay_ms(uint32_t delay_ms);

int main(void)
{
    guard_t guard;
    contact_t contact;
    guard_config_t config = guard_default_config();
    board_init(); /* Must initialize outputs to disabled before returning. */
    contact_init(&contact);
    if (!guard_init(&guard, &config, board_millis())) {
        for (;;) {
            board_write_outputs((guard_output_t){0, 0, 1, 1, 0});
            board_delay_ms(100u);
        }
    }
    for (;;) {
        app_sample_t sample = board_poll_distance();
        bool raw_pressed = board_bumper_pressed();
        uint32_t now_ms = board_millis();
        bool pressed = contact_update(&contact, raw_pressed, now_ms, 30u);
        fusion_result_t decision;
        guard_update(&guard, now_ms, sample.available, sample.valid, sample.distance_mm);
        decision = fusion_decide(&guard, pressed, now_ms);
        board_write_outputs(decision.output); /* Exactly one output write per tick. */
        board_delay_ms(10u);
    }
}
