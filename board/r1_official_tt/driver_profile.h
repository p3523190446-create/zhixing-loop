#ifndef DRIVER_PROFILE_H
#define DRIVER_PROFILE_H
typedef struct {int type,deadzone,lines,ratio,diameter_milli,p_milli,i_milli,d_milli,valid;} driver_profile_t;
int driver_profile_parse(const char *text,driver_profile_t *profile);
#endif
