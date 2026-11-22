"""Differential-drive relative odometry, to enable only after physical calibration.

Linorobot-style four-wheel -> left/right velocity -> planar pose. This estimates
wheel motion, not world position; skid steering and slip invalidate accuracy.
"""
import math

class Odometry:
    def __init__(self, track_mm, unit_to_mm_s, forward_signs):
        if not math.isfinite(track_mm) or track_mm<=0 or not math.isfinite(unit_to_mm_s) or unit_to_mm_s<=0:
            raise ValueError('Measured track and measured velocity scale are required')
        if len(forward_signs)!=4 or any(type(x) is not int or x not in (-1,1) for x in forward_signs):
            raise ValueError('Four physically checked wheel directions are required')
        self.track,self.scale,self.signs=track_mm,unit_to_mm_s,forward_signs
        self.x=self.y=self.yaw=0.
        self.previous=None

    def update(self,wheels,at,valid,source_ms):
        if (not valid or len(wheels)!=4 or any(type(v) not in (float,int) or not math.isfinite(v) for v in wheels)
                or not math.isfinite(at) or type(source_ms) is not int):
            self.previous=None
            return dict(valid=False)
        current=(at,source_ms)
        if self.previous is None:
            self.previous=current
            return dict(valid=False,reason='waiting_for_second_sample')
        old_at,old_ms=self.previous
        if source_ms==old_ms:return dict(valid=False,reason='duplicate_sample')
        self.previous=current
        # Use source clock, not HTTP polling time. Reject reset, gaps and wrap;
        # one baseline sample is safer than integrating across unknown intervals.
        dt=(source_ms-old_ms)/1000
        if not 0<dt<=.5 or not 0<at-old_at<=1:
            return dict(valid=False,reason='time_gap_or_source_reset')
        speeds=[v*s*self.scale for v,s in zip(wheels,self.signs)]
        left,right=sum(speeds[:2])/2,sum(speeds[2:])/2
        distance=(left+right)*.5*dt
        angle=(right-left)/self.track*dt
        if abs(angle)<1e-9:
            self.x+=distance*math.cos(self.yaw);self.y+=distance*math.sin(self.yaw)
        else:
            radius=distance/angle
            self.x+=radius*(math.sin(self.yaw+angle)-math.sin(self.yaw))
            self.y-=radius*(math.cos(self.yaw+angle)-math.cos(self.yaw))
        self.yaw=(self.yaw+angle+math.pi)%(2*math.pi)-math.pi
        return dict(valid=True,x_mm=self.x,y_mm=self.y,yaw_rad=self.yaw,
                    estimate_only=True,actuation_enabled=False)
