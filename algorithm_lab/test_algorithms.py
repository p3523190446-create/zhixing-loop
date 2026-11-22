"""Boundary and image checks; generated targets are explicitly synthetic."""
import bootstrap
import json, math, time, unittest
from pathlib import Path
import cv2 as cv
import numpy as np
from core import LineFollower, Vision, WHITE, BLACK
from odometry import Odometry

def status(mask=231,age=1,stamp=1):
    raw=[BLACK[i] if not mask&(1<<i) else WHITE[i] for i in range(8)]
    return dict(connected=True,line=dict(valid=True,raw=raw,digital_mask=mask,age_ms=age,analog_frames=stamp))

class Algorithms(unittest.TestCase):
    def test_stale_disconnect_and_bad_values_have_no_correction(self):
        for age in [500,-1,float('nan'),None]:
            self.assertIsNone(LineFollower().update(status(age=age))['correction'])
        d=status();d['connected']=False
        self.assertFalse(LineFollower().update(d)['valid'])
        for bad in [float('nan'),True,-1,65536]:
            d=status();d['line']['raw'][0]=bad
            self.assertFalse(LineFollower().update(d)['valid'])

    def test_center_endpoints_and_junctions(self):
        self.assertAlmostEqual(LineFollower().update(status())['position'],0)
        self.assertLess(LineFollower().update(status(254))['correction'],0)
        self.assertGreater(LineFollower().update(status(127))['correction'],0)
        for mask,state in [(255,'no_line'),(0,'all_black'),(250,'junction'),(224,'junction')]:
            d=LineFollower().update(status(mask))
            self.assertEqual(d['state'],state);self.assertIsNone(d['correction'])

    def test_duplicate_is_not_new_derivative_and_gap_resets(self):
        f=LineFollower();a=f.update(status(254),1)
        b=f.update(status(254),1.2)
        self.assertEqual(a['correction'],b['correction'])
        f.update(status(age=600),1.3)
        c=f.update(status(127,stamp=2),1.4)
        self.assertAlmostEqual(c['correction'],.45)
        self.assertFalse(c['actuation_enabled'])

    def test_color_tag_and_motion_on_generated_images(self):
        v=Vision()
        image=np.full((480,640,3),255,np.uint8)
        cv.rectangle(image,(20,100),(140,220),(0,0,255),-1)
        tag=cv.aruco.generateImageMarker(cv.aruco.getPredefinedDictionary(cv.aruco.DICT_APRILTAG_36h11),7,180)
        image[120:300,350:530]=cv.cvtColor(tag,cv.COLOR_GRAY2BGR)
        d,_=v.process(image,1)
        self.assertEqual(d['colors'][0]['color'],'red')
        self.assertLess(d['colors'][0]['offset_x'],0)
        self.assertEqual([t['id'] for t in d['tags']],[7])
        self.assertFalse(d['tags'][0]['station_arrived'])
        self.assertIsNone(d['motion_fraction'])
        scaled,_=Vision().process(cv.resize(image,(960,720)),1)
        self.assertEqual([t['id'] for t in scaled['tags']],[7])
        self.assertAlmostEqual(scaled['colors'][0]['bbox'][0],30,delta=2)
        self.assertAlmostEqual(scaled['colors'][0]['offset_x'],d['colors'][0]['offset_x'],delta=.01)
        d,_=v.process(image,1.2);self.assertEqual(d['motion_fraction'],0)
        d,_=v.process(np.zeros_like(image),1.4);self.assertTrue(d['motion_event'])
        d,_=v.process(image,5);self.assertIsNone(d['motion_fraction'])

    def test_relative_odometry_uses_source_clock_and_rejects_gaps(self):
        o=Odometry(200,1,[1,1,1,1])
        self.assertFalse(o.update([100]*4,1,True,1000)['valid'])
        d=o.update([100]*4,1.1,True,1100)
        self.assertAlmostEqual(d['x_mm'],10);self.assertAlmostEqual(d['yaw_rad'],0)
        self.assertFalse(o.update([100]*4,1.2,True,1100)['valid'])
        self.assertFalse(o.update([100]*4,3,True,3000)['valid'])
        self.assertFalse(o.update([100]*4,3.1,True,5)['valid'])

    def test_viewer_ages_line_and_vision_independently(self):
        import threading
        from unittest.mock import patch
        from server import Lab
        lab=Lab.__new__(Lab);lab.lock=threading.Lock();lab.image_at=9.9;lab.local_camera=None
        lab.data=dict(updated_monotonic=9.8,connected=True,vision_valid=True,vision={'objects':[]},
                      source_age_ms=1400,tracking=dict(state='TRACKING',pointing_request={'image_x':.2},bbox=[1,1,2,2]),
                      line=dict(age_ms=400,valid=True,state='line',position=0,correction=0))
        with patch('server.time.monotonic',return_value=10.1):
            d=lab.state()
        self.assertFalse(d['line']['valid']);self.assertIsNone(d['line']['correction'])
        self.assertFalse(d['vision_valid']);self.assertIsNone(d['vision'])
        self.assertEqual(d['tracking']['state'],'STALE');self.assertIsNone(d['tracking']['pointing_request'])
        self.assertTrue(lab.data['line']['valid'])

if __name__=='__main__':unittest.main()
