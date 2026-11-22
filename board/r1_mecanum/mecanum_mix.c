#include "mecanum_mix.h"
int mecanum_mix(int32_t f,int32_t x,int32_t r,int32_t out[4])
{
    int32_t v[4],peak=250,a;unsigned i;
    if(f < -250||f > 250||x < -250||x > 250||r < -250||r > 250)return 0;
    v[0]=f+x+r;v[1]=f-x+r;v[2]=f-x-r;v[3]=f+x-r;
    for(i=0;i<4;i++){a=v[i]<0?-v[i]:v[i];if(a>peak)peak=a;}
    for(i=0;i<4;i++)out[i]=v[i]*250/peak;
    return 1;
}
