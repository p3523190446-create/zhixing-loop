#include "wheel_control.h"
#include <string.h>
/* Official $spd range is +/-1000. Inputs are normalized +/-250, never PWM.
 * 60 is the observed loaded working floor, not a manufacturer's minimum.
 * Driver default PID/deadzone remain intact. */
typedef struct
{
    int sign, phase;
    unsigned began, moved, brake;
} wheel_t;
static wheel_t wheels[4];
static unsigned last_step;
static int have_step;
volatile int32_t wheel_outputs[4], wheel_targets[4];
volatile uint32_t wheel_fault;
static int absolute(int x)
{
    return x < 0 ? -x : x;
}
void wheel_control_stop(void)
{
    unsigned i;
    memset(wheels, 0, sizeof(wheels));
    for (i = 0; i < 4; i++)
        wheel_outputs[i] = wheel_targets[i] = 0;
    have_step = 0;
}
void wheel_control_reset(void)
{
    wheel_control_stop();
    wheel_fault = 0;
}
static unsigned fault(unsigned code)
{
    wheel_control_stop();
    wheel_fault = code;
    return code;
}
uint32_t wheel_control_step(uint32_t now, int32_t left, int32_t right,
                            const volatile int32_t speeds[4])
{
    unsigned i, dt = have_step ? (unsigned)(now - last_step) : 20u;
    if (wheel_fault)
        return wheel_fault;
    if (left < -250 || left > 250 || right < -250 || right > 250)
        return fault(65);
    if (dt > 100)
        dt = 100;
    last_step = now;
    have_step = 1;
    for (i = 0; i < 4; i++)
    {
        wheel_t *w = &wheels[i];
        int input = i < 2 ? left : right, speed = speeds[i];
        int sign = input > 0   ? 1
                   : input < 0 ? -1
                               : 0,
            wanted = absolute(input) * 4, previous = absolute(wheel_outputs[i]), command;
        /* Engineering overspeed trip: 1000 command ceiling plus25% margin.
         * This replaces the old320 trip; it is not an official motor rating. */
        if (absolute(speed) > 1250)
            return fault(17 + i);
        if (wanted < 60)
            sign = 0;
        if (!sign)
        {
            memset(w, 0, sizeof(*w));
            wheel_outputs[i] = wheel_targets[i] = 0;
            continue;
        }
        wheel_targets[i] = sign * wanted;
        if (!w->phase || w->sign != sign)
        {
            if (w->phase != 3)
            {
                w->brake = now;
                w->phase = 3;
            }
            wheel_outputs[i] = 0;
            previous = 0;
            if (w->sign || sign * speed < -8)
            {
                if (absolute(speed) > 8)
                {
                    if ((unsigned)(now - w->brake) > 800)
                        return fault(49 + i);
                    continue;
                }
                if (w->sign && (unsigned)(now - w->brake) < 150)
                    continue;
            }
            w->sign = sign;
            w->phase = 1;
            w->began = w->moved = now;
        }
        if (sign * speed > 8)
            w->moved = now;
        if ((unsigned)(now - w->began) >= 300 && sign * speed < -20)
            return fault(33 + i);
        if ((unsigned)(now - w->began) >= 1000 && (unsigned)(now - w->moved) >= 800)
            return fault(1 + i);
        /* 1000 command units/s rising slew; lower requests and STOP apply
         * immediately. The max remains reachable in about one second. */
        command = wanted;
        if (wanted > previous)
        {
            unsigned step = dt ? dt : 1;
            command = previous + (int)step;
            if (command < 60)
                command = 60;
            if (command > wanted)
                command = wanted;
        }
        wheel_outputs[i] = sign * command;
    }
    return 0;
}
