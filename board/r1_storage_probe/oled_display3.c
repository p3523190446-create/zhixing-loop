/* SSD1306 128x64 compatibility test, not confirmed controller identification.
 * Solomon Systech datasheet: page addressing, internal charge pump, 64 MUX.
 * Each refresh sends one 32-byte chunk per loop so ranging/UART keep running. */
#include "debug.h"
#include "oled_probe3.h"
#include "oled_display3.h"
#include "guard.h"
#include "oled_glyphs.h"
#include "vision_status.h"
#include <stdio.h>
#include <string.h>
extern volatile uint32_t guard_state, range_corrected_mm, range_correction_valid;
extern volatile uint32_t warning_mm,warning_ui_active;
extern volatile uint32_t vision_valid,vision_link_valid,vision_class,vision_score;
volatile uint32_t oled_display3_ready, oled_display3_frames, oled_display3_errors;
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
static void compose(uint32_t now)
{
    unsigned i;char value[16];
    const uint16_t *codes=vision_status_label();
    memset(image,0,sizeof(image));
    for(i=0;i<128;i++){pixel(i,0);pixel(i,63);}
    for(i=0;i<64;i++){pixel(0,i);pixel(127,i);}
    glyph(5,2,0x7cfb);glyph(21,2,0x7edf);glyph(37,2,0x72b6);glyph(53,2,0x6001);
    if(warning_ui_active){
        glyph(5,23,0x9884);glyph(21,23,0x8b66);
        snprintf(value,sizeof(value),"%lu",(unsigned long)(warning_mm/10u));
        for(i=0;value[i] && i<2;i++)digit(43+i*12,23,value[i]);
        glyph(78,23,0x5398);glyph(94,23,0x7c73);
    }else{
        glyph(5,23,0x8fd0);glyph(21,23,0x884c);
        snprintf(value,sizeof(value),"%lu",(unsigned long)(now/1000u));
        for(i=0;value[i] && i<7;i++)digit(40+i*12,23,value[i]);
    }
    glyph(5,45,0x89c6);glyph(21,45,0x89c9);
    for(i=0;i<5 && codes[i];i++)glyph(45+16*i,45,codes[i]);
}
void oled_display3_poll(uint32_t now)
{
    static const uint8_t init[]={0xae,0xd5,0x80,0xa8,0x3f,0xd3,0,0x40,0x8d,0x14,
        0x20,2,0xa1,0xc8,0xda,0x12,0x81,0x7f,0xd9,0xf1,0xdb,0x20,0xa4,0xa6,0x2e};
    uint8_t position[3],on=0xaf;
    if(!configured){
        if(attempted && (uint32_t)(now-last_attempt)<2000)return;
        attempted=1;last_attempt=now;
        if(!oled3_ack_3c && !oled3_ack_3d)return;
        address=oled3_ack_3c?0x3c:0x3d;
        if(!oled3_bus_write(address,0,init,sizeof(init))){++oled_display3_errors;return;}
        configured=1;compose(now);offset=0;rendering=1;
    }
    if(!rendering){
        if((uint32_t)(now-last_refresh)<250)return;
        compose(now);offset=0;rendering=1;
    }
    position[0]=(uint8_t)(0xb0+offset/128);
    position[1]=(uint8_t)(offset%128 & 15);
    position[2]=(uint8_t)(0x10 | (offset%128 >> 4));
    if(!oled3_bus_write(address,0,position,3) || !oled3_bus_write(address,0x40,image+offset,32)){
        ++oled_display3_errors;configured=0;rendering=0;oled_display3_ready=0;return;
    }
    offset+=32;
    if(offset==sizeof(image)){
        if(!oled_display3_ready && !oled3_bus_write(address,0,&on,1)){
            ++oled_display3_errors;configured=0;rendering=0;return;
        }
        oled_display3_ready=1;++oled_display3_frames;rendering=0;last_refresh=now;
    }
}
