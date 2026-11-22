#ifndef ZXR_VISION_STATUS_H
#define ZXR_VISION_STATUS_H
#include <stdint.h>
extern volatile uint32_t phone_monitor_valid,phone_monitor_state;
extern volatile uint32_t vision_valid,vision_link_valid;
static const uint16_t *vision_status_label(void)
{
    static const uint16_t relay_off[]={0x8f6c,0x53d1,0x79bb,0x7ebf,0};
    static const uint16_t phone_off[]={0x624b,0x673a,0x79bb,0x7ebf,0};
    static const uint16_t app_off[]={0x7a0b,0x5e8f,0x672a,0x8fd0,0x884c,0};
    static const uint16_t no_data[]={0x65e0,0x65b0,0x6570,0x636e,0};
    static const uint16_t empty[]={0x65e0,0x76ee,0x6807,0};
    static const uint16_t target[]={0x6709,0x76ee,0x6807,0};
    if(vision_link_valid)return vision_valid?target:empty;
    if(!phone_monitor_valid)return relay_off;
    if(phone_monitor_state==0)return phone_off;
    if(phone_monitor_state==1)return app_off;
    return no_data;
}
#endif
