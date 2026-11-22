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
/* v2: CRC covers version, sequence, distance AND saved sound mode.
 * v1 distance-only records remain readable, with audible default. */
static inline void setting_encode(uint8_t *p,uint32_t seq,uint16_t mm,uint8_t muted)
{uint16_t inv=(uint16_t)~mm;memset(p,255,32);memcpy(p,"ZXR1",4);setting_put32(p+4,2);setting_put32(p+8,seq);p[12]=(uint8_t)mm;p[13]=(uint8_t)(mm>>8);p[14]=(uint8_t)inv;p[15]=(uint8_t)(inv>>8);p[16]=muted;p[17]=(uint8_t)~muted;setting_put32(p+24,setting_crc(p,24));p[31]=0xA5;}
static inline int setting_decode(const uint8_t *p,uint32_t *seq,uint16_t *mm,uint8_t *muted)
{unsigned i;uint8_t mode=0;uint32_t version=setting_u32(p+4);uint16_t v=(uint16_t)(p[12]|((uint16_t)p[13]<<8));uint16_t inv=(uint16_t)(p[14]|((uint16_t)p[15]<<8));
 if(!setting_magic(p)||p[31]!=0xA5||v<120||v>500||v%10||((uint16_t)(v^inv))!=0xFFFFu)return 0;
 if(version==1){
  if(setting_u32(p+16)!=setting_crc(p,16))return 0;
  for(i=20;i<31;i++)if(p[i]!=255)return 0;
 }else if(version==2){
  mode=p[16];if(mode>1||(uint8_t)(mode^p[17])!=255||setting_u32(p+24)!=setting_crc(p,24))return 0;
  for(i=18;i<24;i++)if(p[i]!=255)return 0;
  for(i=28;i<31;i++)if(p[i]!=255)return 0;
 }else return 0;
 *seq=setting_u32(p+8);*mm=v;*muted=mode;return 1;}
#endif
