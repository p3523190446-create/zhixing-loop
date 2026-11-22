#include "driver_profile.h"
#include <string.h>
#include <stdlib.h>
static int number(const char *text, const char *key, int scale, int *value)
{
    const char *p = strstr(text, key);
    char *end;
    double n;
    if (!p)
        return 0;
    p += strlen(key);
    n = strtod(p, &end);
    if (end == p || n != n || n < 0 || n > 10000)
        return 0;
    if (*end && *end != ' ' && *end != '\t' && *end != '\r' && *end != '\n')
        return 0;
    if (scale == 1 && n != (int)n)
        return 0;
    *value = (int)(n * scale + 0.5);
    return 1;
}
int driver_profile_parse(const char *text, driver_profile_t *v)
{
    memset(v, 0, sizeof(*v));
    if (!strstr(text, "read_flash:OK!"))
        return 0;
    if (!number(text, "Motor_type:", 1, &v->type) || !number(text, "Dead_Zone:", 1, &v->deadzone) ||
        !number(text, "Pulse_Line:", 1, &v->lines) || !number(text, "Pulse_Phase:", 1, &v->ratio) ||
        !number(text, "wheel_diameter:", 1000, &v->diameter_milli) ||
        !number(text, "P:", 1000, &v->p_milli) || !number(text, "I:", 1000, &v->i_milli) ||
        !number(text, "D:", 1000, &v->d_milli))
        return 0;
    /* Matched TT wiring/profile and manufacturer's default PID. Deadzone is
     * read from the real driver, never invented or overwritten here. */
    v->valid = v->type == 3 && v->lines == 13 && v->ratio == 45 && v->diameter_milli == 65000 &&
               v->deadzone >= 0 && v->deadzone <= 3600 && v->p_milli == 800 && v->i_milli == 60 &&
               v->d_milli == 500;
    return v->valid;
}
