/* SSD1306 128x64 compatibility test, not confirmed controller identification.
 * Solomon Systech datasheet: page addressing, internal charge pump, 64 MUX.
 * Each refresh sends one 32-byte chunk per loop so ranging/UART keep running. */
#include "debug.h"
#include "oled_probe2.h"
#include "oled_display2.h"
#include "guard.h"
#include "oled_glyphs.h"
#include "motor_probe.h"
#include "motor_telemetry.h"
#include <stdio.h>
#include <string.h>
volatile uint32_t oled_display2_ready, oled_display2_frames, oled_display2_errors;
static uint8_t image[1024], configured, rendering, address=0x3c;
static unsigned offset;
static uint32_t last_refresh, last_attempt;
static uint8_t attempted;

static void pixel(unsigned x,unsigned y)
{
    if(x<128 && y<64)image[(y/8)*128+x]|=(uint8_t)(1u<<(y%8));
}
static void glyph(unsigned x,unsigned y,uint16_t code)
{
    unsigned i,col,row;
    for(i=0;i<OLED_GLYPH_COUNT;i++)if(oled_glyph_codes[i]==code){
        for(col=0;col<16;col++)for(row=0;row<16;row++)
            if(oled_glyphs[i][col+(row/8)*16]&(1u<<(row%8)))pixel(x+col,y+row);
        return;
    }
}
static const uint8_t numbers[12][5]={
    {0x3e,0x51,0x49,0x45,0x3e},{0,0x42,0x7f,0x40,0},{0x42,0x61,0x51,0x49,0x46},
    {0x21,0x41,0x45,0x4b,0x31},{0x18,0x14,0x12,0x7f,0x10},{0x27,0x45,0x45,0x45,0x39},
    {0x3c,0x4a,0x49,0x49,0x30},{1,0x71,9,5,3},{0x36,0x49,0x49,0x49,0x36},
    {6,0x49,0x49,0x29,0x1e},{0,0x60,0x60,0,0},{8,8,8,8,8}};
static void digit(unsigned x,unsigned y,char ch)
{
    unsigned col,row,dx,dy,index=ch=='.'?10:ch=='-'?11:(unsigned)(ch-'0');
    if(index>11)return;
    for(col=0;col<5;col++)for(row=0;row<7;row++)if(numbers[index][col]&(1u<<row))
        for(dx=0;dx<2;dx++)for(dy=0;dy<2;dy++)pixel(x+2*col+dx,y+2*row+dy);
}
/* Compact ASCII for wheel rows; full Chinese font retained for title/status. */
static void small(unsigned x,unsigned y,const char *s)
{
    static const uint8_t m[]={0x7f,2,4,2,0x7f},v[]={0x1f,0x20,0x40,0x20,0x1f};
    static const uint8_t lower_m[]={0x7c,4,0x18,4,0x78},slash[]={0x20,0x10,8,4,2};
    static const uint8_t lower_s[]={0x48,0x54,0x54,0x54,0x20},colon[]={0,0x36,0x36,0,0};
    unsigned col,row;const uint8_t *bits;
    for(;*s;s++,x+=6){
        bits=0;
        if(*s>='0' && *s<='9')bits=numbers[*s-'0'];
        else if(*s=='-')bits=numbers[11];else if(*s=='.')bits=numbers[10];
        else if(*s=='M')bits=m;else if(*s=='V')bits=v;else if(*s=='m')bits=lower_m;
        else if(*s=='/')bits=slash;else if(*s=='s')bits=lower_s;else if(*s==':')bits=colon;
        if(bits)for(col=0;col<5;col++)for(row=0;row<7;row++)
            if(bits[col]&(1u<<row))pixel(x+col,y+row);
    }
}
static void compose(uint32_t now)
{
    unsigned i,state;char value[16];int32_t speeds[4];
    static const uint16_t status[4][2]={{0x672a,0x8fde},{0x5f85,0x673a},{0x8f6c,0x52a8},{0x6545,0x969c}};
    static const unsigned order[4]={0,2,1,3}; /* actual left/right, front/rear */
    int vf=motor_value_fresh(now,motor_voltage_last_ms,motor_voltage_frames,3000u);
    int sf=motor_encoder_upload_enabled && motor_value_fresh(now,motor_speed_last_ms,motor_speed_frames,500u);
    for(i=0;i<4;i++)speeds[i]=motor_speed_values[i];
    state=motor_dashboard_state(sf,speeds,motor_pulse_active,motor_fault_cause,
        motor_rx_errors,motor_rx_drops,vf,motor_voltage_mv);
    memset(image,0,sizeof(image));
    for(i=0;i<128;i++){pixel(i,0);pixel(i,35);pixel(i,63);}
    for(i=0;i<64;i++){pixel(0,i);pixel(127,i);if(i>35)pixel(64,i);}
    glyph(5,2,0x7535);glyph(21,2,0x538b); /* 电压 */
    if(vf)snprintf(value,sizeof(value),"%lu.%02lu",(unsigned long)(motor_voltage_mv/1000u),
        (unsigned long)((motor_voltage_mv%1000u)/10u));
    else strcpy(value,"--.--");
    for(i=0;value[i] && i<5;i++)digit(41+i*12,2,value[i]);
    small(41+i*12,7,"V");
    glyph(5,19,0x8f6e);glyph(21,19,0x901f);small(41,24,"mm/s");
    glyph(90,19,status[state][0]);glyph(106,19,status[state][1]);
    for(i=0;i<4;i++){
        unsigned wheel=order[i];
        if(sf)snprintf(value,sizeof(value),"M%u:%5ld",wheel+1,(long)speeds[wheel]);
        else snprintf(value,sizeof(value),"M%u:   --",wheel+1);
        small(i%2?73:8,i<2?39:53,value);
    }
}
void oled_display2_poll(uint32_t now)
{
    static const uint8_t init[]={0xae,0xd5,0x80,0xa8,0x3f,0xd3,0,0x40,0x8d,0x14,
        0x20,2,0xa1,0xc8,0xda,0x12,0x81,0x7f,0xd9,0xf1,0xdb,0x20,0xa4,0xa6,0x2e};
    uint8_t position[3],on=0xaf;
    if(!configured){
        if(attempted && (uint32_t)(now-last_attempt)<2000)return;
        attempted=1;last_attempt=now;
        if(!oled2_ack_3c && !oled2_ack_3d)return;
        address=oled2_ack_3c?0x3c:0x3d;
        if(!oled2_bus_write(address,0,init,sizeof(init))){++oled_display2_errors;return;}
        configured=1;compose(now);offset=0;rendering=1;
    }
    if(!rendering){
        if((uint32_t)(now-last_refresh)<250)return;
        compose(now);offset=0;rendering=1;
    }
    position[0]=(uint8_t)(0xb0+offset/128);
    position[1]=(uint8_t)(offset%128 & 15);
    position[2]=(uint8_t)(0x10 | (offset%128 >> 4));
    if(!oled2_bus_write(address,0,position,3) || !oled2_bus_write(address,0x40,image+offset,32)){
        ++oled_display2_errors;configured=0;rendering=0;oled_display2_ready=0;return;
    }
    offset+=32;
    if(offset==sizeof(image)){
        if(!oled_display2_ready && !oled2_bus_write(address,0,&on,1)){
            ++oled_display2_errors;configured=0;rendering=0;return;
        }
        oled_display2_ready=1;++oled_display2_frames;rendering=0;last_refresh=now;
    }
}
