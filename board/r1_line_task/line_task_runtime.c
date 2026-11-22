#include "line_task_runtime.h"
#include "line_task.h"
#include "line_tracking.h"
#include "remote_drive.h"
#include <stdio.h>
#include <string.h>
/* Ground permission remains off until the independent stop and installation are accepted.
 * This build is reviewable software, not a claim that unplugging the driver wire stops it. */
#ifndef LINE_TASK_GROUND_READY
#define LINE_TASK_GROUND_READY 0
#endif
#ifndef LINE_TASK_LOW_SPEED_TRIAL
#define LINE_TASK_LOW_SPEED_TRIAL 0
#endif
#ifndef LINE_TASK_LOOP_ENABLED
#define LINE_TASK_LOOP_ENABLED 0
#endif
extern volatile uint32_t led_last_good_ms, range_correction_valid, range_corrected_mm, warning_mm;
extern int remote_drive_task_begin(uint32_t now, int uart_owner);
extern int remote_drive_task_set(uint32_t now, int left, int right);
static lt_task task;
static lt_config config = {0, LT_STOP, 60, 10000};
/* 只收到KEEPALIVE才续租，读取STATUS不会延长运动请求。 */
static uint32_t lease_at, last_step;
/* 配置与标定共用有上限的十进制解析，拒绝溢出、符号和多余字段。 */
static int number(const char **text, unsigned *out, unsigned limit, char end)
{
    unsigned value = 0;
    const char *p = *text;
    if (*p < '0' || *p > '9')
        return 0;
    while (*p >= '0' && *p <= '9')
    {
        unsigned digit = (unsigned)(*p - '0');
        if (value > (limit - digit) / 10u)
            return 0;
        value = value * 10u + digit;
        ++p;
    }
    if (*p != end)
        return 0;
    *text = p + (end ? 1 : 0);
    *out = value;
    return 1;
}
static int parse_config(const char *p, int *side, unsigned *branch, unsigned *speed, unsigned *ms)
{
    if (!strncmp(p, "1,", 2))
    {
        *side = 1;
        p += 2;
    }
    else if (!strncmp(p, "-1,", 3))
    {
        *side = -1;
        p += 3;
    }
    else
        return 0;
    return number(&p, branch, 10000u, ',') && number(&p, speed, 10000u, ',') &&
           number(&p, ms, 10000u, 0);
}
int line_task_running(void)
{
    return lt_active(&task);
}
static int permitted(uint32_t now)
{
    /* Floor-loop driving is operator supervised, like existing manual mode.
     * Forward ToF often returns invalid at bends/open space; it is advisory
     * here. Motor feedback, voltage, sensor freshness and lease stay enforced. */
    if (LINE_TASK_LOOP_ENABLED && config.branch == LT_LOOP)
        return 1;
    return range_correction_valid && (uint32_t)(now - led_last_good_ms) < 300 &&
           range_corrected_mm > warning_mm;
}
void line_task_poll(uint32_t now)
{
    lt_input input;
    if (!line_task_running())
        return;
    if ((uint32_t)(now - lease_at) >= 500 || !remote_drive_armed)
    {
        task.left = task.right = 0;
        task.state = LT_FAULT;
        task.reason = remote_drive_armed ? LT_LEASE_EXPIRED : LT_DRIVE_FAULT;
        if (remote_drive_armed) remote_drive_stop(1);
        return;
    }
    if ((uint32_t)(now - last_step) < 20)
        return;
    last_step = now;
    line_tracking_task_input(now, &input);
    lt_classify(&input);
    input.permit = (uint8_t)permitted(now);
    lt_step(&task, &input, now);
    if (!line_task_running() || !remote_drive_task_set(now, task.left, task.right))
    {
        if (line_task_running()) {
            task.left = task.right = 0;
            task.state = LT_FAULT;
            task.reason = LT_DRIVE_FAULT;
        }
        if (remote_drive_armed) remote_drive_stop(5);
    }
}
static int calibration_values(const char *p, uint16_t *f, uint16_t *b)
{
    unsigned i;
    for (i = 0; i < 16; i++)
    {
        unsigned value;
        if (!number(&p, &value, 65535u, i == 15 ? 0 : ','))
            return 0;
        if (i < 8)
            f[i] = (uint16_t)value;
        else
            b[i - 8] = (uint16_t)value;
    }
    return 1;
}
static int valid_config(int side, unsigned branch, unsigned speed, unsigned ms)
{
    lt_config candidate = {side, branch, speed, ms};
    return lt_config_valid(&candidate);
}
static int task_command(const char *text, uint32_t now, void (*reply)(const char *), int uart_owner)
{
    char out[180];
    int side;
    unsigned branch, speed, ms;
    lt_input input;
    if (strncmp(text, "LINE_TASK_", 10))
        return 0;
    if (!strcmp(text, "LINE_TASK_CAL_CAPS"))
        reply("LINE_TASK_CAL_CAPS,1,8\n");
    else if (!strcmp(text,"LINE_TASK_LOOP"))
    {
        snprintf(out,sizeof(out),"LINE_TASK_LOOP,%u,40,0\n",(unsigned)LINE_TASK_LOOP_ENABLED);reply(out);
    }
    else if (!strcmp(text, "LINE_TASK_TRIAL"))
    {
        snprintf(out,sizeof(out),"LINE_TASK_TRIAL,%u,40,5000\n",(unsigned)LINE_TASK_LOW_SPEED_TRIAL);reply(out);
    }
    else if (!strcmp(text, "LINE_TASK_CAL_GET"))
    {
        uint16_t f[8], b[8];
        unsigned i, at;
        uint32_t id = lt_get_calibration(f, b);
        at = (unsigned)snprintf(out, sizeof(out), "LINE_TASK_CAL,%lu", (unsigned long)id);
        for (i = 0; i < 16; i++)
            at += (unsigned)snprintf(out + at, sizeof(out) - at, ",%u", i < 8 ? f[i] : b[i - 8]);
        snprintf(out + at, sizeof(out) - at, "\n");
        reply(out);
    }
    else if (!strncmp(text, "LINE_TASK_CAL_SET,", 18))
    {
        uint16_t f[8], b[8];
        if (line_task_running() || remote_drive_armed || !calibration_values(text + 18, f, b) ||
            !lt_set_calibration(f, b))
            reply("ERR,LINE_TASK_CAL_INVALID_OR_BUSY\n");
        else
        {
            snprintf(out, sizeof(out), "LINE_TASK_CAL_SAVED,%lu\n",
                     (unsigned long)lt_get_calibration(f, b));
            reply(out);
        }
    }
    else if (!strcmp(text, "LINE_TASK_CAPS"))
    {
        snprintf(out, sizeof(out), "LINE_TASK_CAPS,1,50,100,%u\n",
                 (unsigned)LINE_TASK_GROUND_READY);
        reply(out);
    }
    else if (!strcmp(text, "LINE_TASK_STATUS"))
    {
        snprintf(out, sizeof(out), "LINE_TASK_STATUS,%lu,%u,%u,%u,%d,%d,%d,%u,%u,%u\n",
                 (unsigned long)now, task.state, task.reason, task.junctions, task.left, task.right,
                 config.x1_left, config.branch, config.speed, config.max_ms);
        reply(out);
    }
    else if (!strcmp(text, "LINE_TASK_STOP"))
    {
        lt_stop(&task);
        remote_drive_stop(5);
        reply("LINE_TASK_STOPPED\n");
    }
    else if (!strncmp(text, "LINE_TASK_CONFIG,", 17))
    {
        if (line_task_running() || remote_drive_armed ||
            !parse_config(text + 17, &side, &branch, &speed, &ms) ||
            !valid_config(side, branch, speed, ms) ||
            (LINE_TASK_LOW_SPEED_TRIAL && (speed != 40 || ms > 5000 || branch != LT_STOP)) ||
            (!LINE_TASK_LOOP_ENABLED && branch == LT_LOOP) ||
            (LINE_TASK_LOOP_ENABLED && speed > 40))
            reply("ERR,LINE_TASK_CONFIG\n");
        else
        {
            config.x1_left = side;
            config.branch = branch;
            config.speed = speed;
            config.max_ms = ms;
            reply("LINE_TASK_CONFIGURED\n");
        }
    }
    else if (!strcmp(text, "LINE_TASK_START"))
    {
        if (!LINE_TASK_GROUND_READY || line_task_running() || remote_drive_armed)
        {
            reply("ERR,LINE_TASK_GROUND_NOT_ACCEPTED_OR_BUSY\n");
            return 1;
        }
        if (!lt_calibration_ready())
        {
            reply("ERR,LINE_TASK_CAL_REQUIRED\n");
            return 1;
        }
        line_tracking_task_input(now, &input);
        lt_classify(&input);
        input.permit = (uint8_t)permitted(now);
        if (!lt_start(&task, &config, &input, now))
        {
            reply("ERR,LINE_TASK_INPUT_OR_CONFIG\n");
            return 1;
        }
        if (!remote_drive_task_begin(now, uart_owner))
        {
            lt_stop(&task);
            reply("ERR,LINE_TASK_DRIVER\n");
            return 1;
        }
        lease_at = now;
        last_step = now;
        reply("LINE_TASK_STARTED\n");
    }
    else if (!strcmp(text, "LINE_TASK_KEEPALIVE"))
    {
        if (!line_task_running())
            reply("ERR,LINE_TASK_NOT_RUNNING\n");
        else
        {
            lease_at = now;
            reply("LINE_TASK_ALIVE\n");
        }
    }
    else
        reply("ERR,LINE_TASK_COMMAND\n");
    return 1;
}
int line_task_command(const char *text, uint32_t now, void (*reply)(const char *))
{
    return task_command(text, now, reply, 1);
}
int line_task_usb_command(const char *text, uint32_t now, void (*reply)(const char *))
{
    return task_command(text, now, reply, 0);
}
