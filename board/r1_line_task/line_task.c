#include "line_task.h"
#include <string.h>
/* 旧场景参考用于初始显示；适配器在calibrated为0时禁止启动。
 * 真实地砖/胶带参考须由手机现场采样后整组下发。 */
static uint16_t white[8] = {220, 246, 251, 248, 249, 258, 258, 226};
static uint16_t black[8] = {3145, 3452, 3456, 3414, 3331, 3352, 3357, 2969};
static uint8_t calibrated;
static uint32_t calibration_id;
int lt_set_calibration(const uint16_t *floor, const uint16_t *dark)
{
    unsigned i, j;
    uint32_t h = 2166136261u;
    for (i = 0; i < 8; i++)
        if ((int)dark[i] - (int)floor[i] < 300)
            return 0;
    /* FNV32须与手机逐字节一致，仅校验内容，不是安全认证。 */
    for (j = 0; j < 2; j++)
        for (i = 0; i < 8; i++)
        {
            uint16_t n = j ? dark[i] : floor[i];
            h = (h ^ (n & 255u)) * 16777619u;
            h = (h ^ (n >> 8)) * 16777619u;
        }
    memcpy(white, floor, sizeof(white));
    memcpy(black, dark, sizeof(black));
    calibration_id = h;
    calibrated = 1;
    return 1;
}
int lt_calibration_ready(void)
{
    return calibrated;
}
uint32_t lt_get_calibration(uint16_t *floor, uint16_t *dark)
{
    memcpy(floor, white, sizeof(white));
    memcpy(dark, black, sizeof(black));
    return calibration_id;
}
void lt_classify(lt_input *p)
{
    unsigned i;
    if (!calibrated)
        return;
    p->white_mask = 0;
    for (i = 0; i < 8; i++)
        if ((int)p->raw[i] - (int)white[i] < ((int)black[i] - (int)white[i] + 1) / 2)
            p->white_mask |= (uint8_t)(1u << i);
}
int lt_config_valid(const lt_config *c)
{
    return (c->x1_left == 1 || c->x1_left == -1) && c->branch <= LT_LOOP &&
           c->speed >= LT_MIN_SPEED && c->speed <= LT_MAX_SPEED &&
           ((c->branch == LT_LOOP && c->max_ms == 0) ||
            (c->max_ms >= LT_MIN_DURATION_MS && c->max_ms <= LT_MAX_DURATION_MS));
}

static int clamp(int x, int n)
{
    return x < -n ? -n : x > n ? n : x;
}
static void halt(lt_task *s, unsigned state, unsigned reason)
{
    s->left = s->right = 0;
    s->state = state;
    s->reason = reason;
    s->have_previous = 0;
}
void lt_init(lt_task *s)
{
    memset(s, 0, sizeof(*s));
}
int lt_active(const lt_task *s)
{
    return s->state >= LT_FOLLOW && s->state <= LT_TURN;
}
void lt_stop(lt_task *s)
{
    /* STOP still zeros outputs, but must not erase the first fault/done reason. */
    if (s->state == LT_FAULT || s->state == LT_DONE) {
        s->left = s->right = 0;
        return;
    }
    halt(s, LT_IDLE, LT_CANCELLED);
}
static int fresh(const lt_input *p)
{
    return p->valid && p->analog_frames && p->digital_frames && p->analog_age < 150 &&
           p->digital_age < 150;
}
/* white_mask的1表示地面，0表示黑线；统计探头数和连续黑段数。 */
static unsigned shape(const lt_input *p, unsigned *segments)
{
    unsigned n = 0, i;
    int prev = 0;
    *segments = 0;
    for (i = 0; i < 8; i++)
    {
        int d = !(p->white_mask & (1u << i));
        n += d;
        if (d && !prev)
            ++*segments;
        prev = d;
    }
    return n;
}
/* Adapted weighted-position/last-side approach from Pololu QTRSensors::readLinePrivate
 * (https://github.com/pololu/qtr-sensors-arduino). Sensor I/O remains Yahboom UART.
 * Search time, confidence, speed scheduling and guard behavior are this vehicle's code. */
static int loop_position(const lt_input *p, int side, float *position)
{
    float sum=0, weight=0, maximum=0;unsigned i;
    for(i=0;i<8;i++){
        float v=((float)p->raw[i]-white[i])/((float)black[i]-white[i]);
        if(v<0)v=0;if(v>1)v=1;if(v>maximum)maximum=v;
        if(v>.1f){float w=v-.1f;weight+=w;sum+=w*(2.0f*i/7.0f-1);}
    }
    if(maximum<.25f||weight<.12f)return 0;
    *position=sum/weight*side;return 1;
}
static float magnitude(float x){return x<0?-x:x;}
static void loop_follow(lt_task *s,const lt_input *p,uint32_t now,uint32_t dt,unsigned n,unsigned segments)
{
    float pos=0,derivative=0,base,correction;int visible=loop_position(p,s->config.x1_left,&pos);
    if(!visible){
        s->stable_since=now;s->reacquire_samples=0;
        if(!s->recovery_budget){s->recovery_budget=1;s->recover_began=now;}
        s->recovering=1;s->state=LT_TURN;s->have_previous=0;s->loop_derivative=0;
        /* User-owned continuous mode: no lost-line task cancellation. Do not
         * drive forward blindly. Search at low speed while heartbeat is alive. */
        if(!s->last_side){
            uint32_t elapsed=(uint32_t)(now-s->recover_began);
            if(elapsed<100){s->left=s->right=20;return;}
            /* No prior heading: alternate widening angular sweeps about the
             * initial heading (left .5s, right 1s, left 1.5s, ...). */
            uint32_t leg=500;int side=-1;elapsed-=100;
            while(elapsed>=leg&&leg<3000){elapsed-=leg;leg+=500;side=-side;}
            if(leg>=3000)side=((elapsed/3000)&1)?-side:side;
            s->left=side*22;s->right=-s->left;return;
        }
        s->left=s->last_side<0?-24:24;s->right=-s->left;return;
    }
    if(s->recovering){
        /* Edge probes are valid reacquisition too. Waiting for central probes
         * kept pivoting past a recovered line on tight bends. */
        ++s->reacquire_samples;
        if(s->reacquire_samples<2)return;
        s->recovering=0;s->state=LT_FOLLOW;s->stable_since=now;s->have_previous=0;
    }
    if(s->recovery_budget&&(uint32_t)(now-s->stable_since)>=300)s->recovery_budget=0;
    /* Broad / split tape is ambiguous, not a requested stop in loop mode.
       Prefer the black segment nearest the previous line, avoiding a midpoint
       between two separate branches. All black retains the last heading. */
    if(n>=7||segments>1){
        unsigned i=0;float best=3,chosen=s->position;
        s->broad_active=1;
        if(n<7)while(i<8){
            unsigned first,last;float candidate,distance;
            if(p->white_mask&(1u<<i)){++i;continue;}
            first=last=i++;while(i<8&&!(p->white_mask&(1u<<i)))last=i++;
            candidate=((float)(first+last)/7-1)*s->config.x1_left;
            distance=magnitude(candidate-s->position);
            if(distance<best){best=distance;chosen=candidate;}
        }
        pos=chosen;
    }else s->broad_active=0;
    if(s->have_previous){derivative=(pos-s->previous)*1000/dt;if(derivative>6)derivative=6;if(derivative< -6)derivative=-6;}
    s->loop_derivative=.45f*derivative+.55f*s->loop_derivative;
    s->previous=pos;s->position=pos;s->have_previous=1;
    if(magnitude(pos)>.12f){s->last_side=pos<0?-1:1;s->direction_at=now;}
    base=(float)s->config.speed-18*magnitude(pos)-2*magnitude(s->loop_derivative);
    if(base<24)base=24;if(s->broad_active)base=20;
    correction=60*pos+1.2f*s->loop_derivative;
    s->left=clamp((int)(base+correction),70);s->right=clamp((int)(base-correction),70);
    s->state=LT_FOLLOW;
}
int lt_start(lt_task *s, const lt_config *c, const lt_input *p, uint32_t now)
{
    unsigned segments, n;
    lt_init(s);
    if (!lt_config_valid(c))
    {
        halt(s, LT_FAULT, LT_BAD_CONFIG);
        return 0;
    }
    if (!fresh(p))
    {
        halt(s, LT_FAULT, LT_STALE);
        return 0;
    }
    if (!p->permit)
    {
        halt(s, LT_FAULT, LT_GUARD);
        return 0;
    }
    n = shape(p, &segments);
    if ((!n || n > 4 || segments != 1) && c->branch != LT_LOOP)
    {
        halt(s, LT_FAULT, LT_LOST);
        return 0;
    }
    s->config = *c;
    if(c->branch==LT_LOOP){float pos;if(!n||!loop_position(p,c->x1_left,&pos)||n>=7||segments>1){halt(s,LT_FAULT,LT_LOST);return 0;}s->position=s->previous=pos;s->have_previous=1;if(magnitude(pos)>.12f){s->last_side=pos<0?-1:1;s->direction_at=now;}}
    s->state = LT_FOLLOW;
    s->began = s->last_update = now;
    s->last_analog = p->analog_frames;
    s->last_digital = p->digital_frames;
    return 1; /* Arming starts at zero; only a new complete sample may produce a request. */
}
void lt_step(lt_task *s, const lt_input *p, uint32_t now)
{
    unsigned n, segments;
    uint32_t dt;
    int center;
    float weight = 0, sum = 0, pos, derivative = 0;
    unsigned i;
    if (!lt_active(s))
        return;
    if (!p->permit)
    {
        halt(s, LT_FAULT, LT_GUARD);
        return;
    }
    if (!fresh(p))
    {
        halt(s, LT_FAULT, LT_STALE);
        return;
    }
    if (s->config.max_ms && (uint32_t)(now - s->began) >= s->config.max_ms)
    {
        halt(s, LT_DONE, LT_TIME_LIMIT);
        return;
    }
    if (s->config.branch != LT_LOOP && s->state == LT_TURN && (uint32_t)(now - s->turn_began) >= 1200)
    {
        halt(s, LT_FAULT, LT_TURN_TIMEOUT);
        return;
    }
    /* A duplicate or half-new analog/digital pair never advances decisions or PD. */
    if (p->analog_frames == s->last_analog || p->digital_frames == s->last_digital)
        return;
    dt = (uint32_t)(now - s->last_update);
    if (dt > 150)
    {
        halt(s, LT_FAULT, LT_STALE);
        return;
    }
    if (dt < 20)
        return;
    s->last_update = now;
    s->last_analog = p->analog_frames;
    s->last_digital = p->digital_frames;
    n = shape(p, &segments);
    if(s->config.branch==LT_LOOP){loop_follow(s,p,now,dt,n,segments);return;}
    center = (p->white_mask & 0x18u) != 0x18u;
    if (s->state == LT_TURN)
    {
        if (!center)
            s->center_clear = 1;
        if (n > 0 && n <= 4 && segments == 1 && center &&
            (s->config.branch == LT_STRAIGHT || s->center_clear) &&
            (uint32_t)(now - s->turn_began) >= 150)
            ++s->center_samples;
        else
            s->center_samples = 0;
        if (s->center_samples >= 2)
        {
            s->state = LT_FOLLOW;
            s->have_previous = 0;
            s->junction_samples = 0;
            s->left = s->right = 0;
        }
        else
            return;
    }
    if (!n)
    {
        halt(s, LT_FAULT, LT_LOST);
        return;
    }
    if (n > 4 || segments > 1)
    {
        s->state = LT_JUNCTION;
        s->left = s->right = 0;
        s->have_previous = 0;
        if (++s->junction_samples < 3)
            return;
        ++s->junctions;
        s->junction_samples = 0;
        if (s->config.branch == LT_STOP)
        {
            halt(s, LT_DONE, LT_AT_JUNCTION);
            return;
        }
        s->state = LT_TURN;
        s->turn_began = now;
        s->center_samples = s->center_clear = 0;
        if (s->config.branch == LT_STRAIGHT)
            s->left = s->right = (int)s->config.speed / 2;
        else
        {
            s->left = s->config.branch == LT_LEFT ? -40 : 40;
            s->right = -s->left;
        }
        return;
    }
    s->junction_samples = 0;
    s->state = LT_FOLLOW;
    for (i = 0; i < 8; i++)
        if (!(p->white_mask & (1u << i)))
        {
            float w = ((float)p->raw[i] - white[i]) / (black[i] - white[i]);
            if (w < .01f)
                w = .01f;
            if (w > 1)
                w = 1;
            sum += w * (2.0f * i / 7.0f - 1);
            weight += w;
        }
    pos = sum / weight * s->config.x1_left;
    if (s->have_previous && dt <= 150)
        derivative = (pos - s->previous) * 1000 / dt;
    s->position = pos;
    s->previous = pos;
    s->have_previous = 1;
    /* 原PD系数、限幅和运算次序保持，本次不改变实物调参。 */
    {
        int correction = clamp((int)(40 * pos + 4 * derivative), 60);
        s->left = clamp((int)s->config.speed + correction, 100);
        s->right = clamp((int)s->config.speed - correction, 100);
    }
}
