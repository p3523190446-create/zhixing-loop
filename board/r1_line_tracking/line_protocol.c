#include "line_protocol.h"
#include <string.h>

void line_protocol_reset_frame(line_protocol_t *p) { p->length=0; }
int line_protocol_fresh(uint32_t frames,uint32_t last,uint32_t now)
{ return frames && (uint32_t)(now-last)<500u; }

static int parse(line_protocol_t *p,uint32_t now)
{
    const char *s=p->frame;
    uint16_t values[8];
    unsigned i,kind;
    if(*s++!='$')return 0;
    kind=(unsigned)*s++;
    if((kind!='A' && kind!='D') || *s++!=',')return 0;
    for(i=0;i<8;i++) {
        unsigned value=0,digits=0;
        if(*s++!='x' || *s++!=(char)('1'+i) || *s++!=':')return 0;
        while(*s>='0' && *s<='9') {
            value=value*10u+(unsigned)(*s++-'0');
            if(++digits>5 || value>65535u)return 0;
        }
        if(!digits || (kind=='D' && value>1u))return 0;
        values[i]=(uint16_t)value;
        if(*s++!=(i==7?'#':','))return 0;
    }
    if(*s)return 0;
    if(kind=='A') {
        memcpy(p->analog,values,sizeof(values));
        ++p->analog_frames;p->analog_ms=now;
    } else {
        for(i=0;i<8;i++)p->digital[i]=(uint8_t)values[i];
        ++p->digital_frames;p->digital_ms=now;
    }
    return 1;
}

void line_protocol_byte(line_protocol_t *p,uint8_t byte,uint32_t now)
{
    if(byte=='$') {
        if(p->length)++p->rejected;
        p->length=1;p->frame[0]='$';return;
    }
    if(!p->length)return;
    if(byte<32u || byte>126u || p->length>=sizeof(p->frame)-1u) {
        ++p->rejected;p->length=0;return;
    }
    p->frame[p->length++]=(char)byte;
    if(byte=='#') {
        p->frame[p->length]=0;
        if(!parse(p,now))++p->rejected;
        p->length=0;
    }
}
