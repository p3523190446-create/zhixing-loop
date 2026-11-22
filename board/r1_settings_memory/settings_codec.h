#ifndef SETTINGS_CODEC_H
#define SETTINGS_CODEC_H
#include <stdint.h>
#include <string.h>
static inline uint32_t setting_crc(const uint8_t *p,unsigned n)
{uint32_t c=0xFFFFFFFFu;unsigned i;while(n--){c^=*p++;for(i=0;i<8;i++)c=(c>>1)^((c&1)?0xEDB88320u:0);}return ~c;}
static inline uint32_t setting_u32(const uint8_t *p)
{return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static inline void setting_put32(uint8_t *p,uint32_t v)
{unsigned i;for(i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));}
static inline int setting_magic(const uint8_t *p)
{return p[0]=='Z' && p[1]=='X' && p[2]=='R' && p[3]=='1';}
static inline void setting_encode(uint8_t *p,uint32_t seq,uint16_t mm)
{uint16_t inv=(uint16_t)~mm;memset(p,255,32);memcpy(p,"ZXR1",4);setting_put32(p+4,1);setting_put32(p+8,seq);p[12]=(uint8_t)mm;p[13]=(uint8_t)(mm>>8);p[14]=(uint8_t)inv;p[15]=(uint8_t)(inv>>8);setting_put32(p+16,setting_crc(p,16));p[31]=0xA5;}
static inline int setting_decode(const uint8_t *p,uint32_t *seq,uint16_t *mm)
{unsigned i;uint16_t v=(uint16_t)(p[12]|((uint16_t)p[13]<<8));uint16_t inv=(uint16_t)(p[14]|((uint16_t)p[15]<<8));
 if(!setting_magic(p)||setting_u32(p+4)!=1||p[31]!=0xA5||v<120||v>500||v%10||((uint16_t)(v^inv))!=0xFFFFu||setting_u32(p+16)!=setting_crc(p,16))return 0;
 for(i=20;i<31;i++)if(p[i]!=255)return 0;
 *seq=setting_u32(p+8);*mm=v;return 1;}
#endif
