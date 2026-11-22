"""Host-side relative level/zero-rate reference. Never changes sensor/actuators."""
import math
def angles(raw):
    ax,ay,az=raw[:3]
    if ax*ax+ay*ay+az*az==0:raise ValueError('Zero acceleration vector has no tilt reference')
    return math.degrees(math.atan2(ay,az)),math.degrees(math.atan2(-ax,math.hypot(ay,az)))
def difference(degrees,reference):
    return (degrees-reference+180)%360-180
def relative(raw,reference):
    roll,pitch=angles(raw)
    gyro=[raw[i+4]-reference['gyro_bias_raw'][i] for i in range(3)]
    return dict(relative_roll_deg=difference(roll,reference['roll_reference_deg']),
        relative_pitch_deg=difference(pitch,reference['pitch_reference_deg']),gyro_delta_raw=gyro,
        assumed_gyro_dps=[x/131 for x in gyro])
