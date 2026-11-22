#ifndef ZX_LINE_TASK_H
#define ZX_LINE_TASK_H
#include <stdint.h>
/* Portable task core. Outputs are bounded requests, never direct motor writes. */
/* 枚举顺序同时用于手机通信，不能随意重排。 */
enum
{
    LT_IDLE,
    LT_FOLLOW,
    LT_JUNCTION,
    LT_TURN,
    LT_DONE,
    LT_FAULT
};
enum
{
    LT_STOP,
    LT_LEFT,
    LT_STRAIGHT,
    LT_RIGHT,
    LT_LOOP
};
enum
{
    LT_OK,
    LT_BAD_CONFIG,
    LT_STALE,
    LT_LOST,
    LT_GUARD,
    LT_TIME_LIMIT,
    LT_AT_JUNCTION,
    LT_TURN_TIMEOUT,
    LT_CANCELLED,
    LT_DRIVE_FAULT,
    LT_LEASE_EXPIRED
};
enum
{
    LT_CHANNELS = 8,
    LT_MIN_SPEED = 40,
    LT_MAX_SPEED = 100,
    LT_MIN_DURATION_MS = 1000,
    LT_MAX_DURATION_MS = 10000,
    LT_SAMPLE_MAX_AGE_MS = 150,
    LT_STEP_MS = 20
};
typedef struct
{
    int x1_left; /* 1: X1在车左；-1: X1在车右；0: 尚未配置。 */
    unsigned branch, speed, max_ms;
} lt_config;
typedef struct
{
    uint16_t raw[8];
    uint8_t white_mask, valid, permit;
    uint32_t analog_age, digital_age, analog_frames, digital_frames;
} lt_input;
typedef struct
{
    lt_config config;
    unsigned state, reason, junctions, junction_samples, center_samples, center_clear;
    uint32_t began, turn_began, last_update, last_analog, last_digital;
    int left, right;
    float position, previous;
    uint8_t have_previous;
    /* Ring-following recovery stays in LT_TURN to preserve the wire state enum. */
    float loop_derivative;
    int last_side;
    uint32_t direction_at, recover_began, stable_since, broad_began;
    uint8_t recovering, recovery_budget, broad_active;
    unsigned reacquire_samples;
} lt_task;
void lt_init(lt_task *s);
int lt_config_valid(const lt_config *config);
int lt_start(lt_task *s, const lt_config *config, const lt_input *p, uint32_t now);
void lt_step(lt_task *s, const lt_input *p, uint32_t now);
void lt_stop(lt_task *s);
int lt_active(const lt_task *s);
int lt_set_calibration(const uint16_t *floor, const uint16_t *dark);
int lt_calibration_ready(void);
uint32_t lt_get_calibration(uint16_t *floor, uint16_t *dark);
void lt_classify(lt_input *p);
#endif
