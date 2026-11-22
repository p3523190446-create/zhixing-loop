#ifndef ZHIXING_MECANUM_MIX_H
#define ZHIXING_MECANUM_MIX_H
#include <stdint.h>
/* Body axes: forward+, right+, clockwise+. Wheel order M1 FL, M2 RL,
 * M3 FR, M4 RR; positive wheel speed means forward travel. X roller layout.
 * Inputs are dimensionless command amplitudes, NOT mm/s or degrees/s.
 * Four wheels share one normalization factor, never independent clipping. */
int mecanum_mix(int32_t forward,int32_t right,int32_t clockwise,int32_t out[4]);
#endif
