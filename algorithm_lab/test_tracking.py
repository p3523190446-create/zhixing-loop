"""Target association, expiry and event boundaries; no camera or actuator I/O."""
import bootstrap
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tracking import TargetTracker
from events import EventStore

def vision(box=None):
    return dict(colors=[dict(color='red',bbox=box)] if box else [],objects=[],tags=[],motion_event=False)

class TrackingChecks(unittest.TestCase):
    def test_lock_three_frames_then_loss_stops_pointing(self):
        t=TargetTracker()
        self.assertEqual(t.update(vision([80,20,10,10]),100,100,20)['state'],'LOCKING')
        t.update(vision([80,20,10,10]),100,100,20)
        d=t.update(vision([81,20,10,10]),100,100,20)
        self.assertEqual(d['state'],'TRACKING');self.assertGreater(d['pointing_request']['image_x'],0)
        self.assertFalse(d['actuation_enabled'])
        d=t.update(vision(),100,100,20)
        self.assertEqual(d['state'],'LOST');self.assertIsNone(d['pointing_request'])

    def test_expiry_pause_bad_config_and_deadzone(self):
        t=TargetTracker()
        for age in [-1,250,float('nan')]:self.assertEqual(t.update(vision([40,40,20,20]),100,100,age)['state'],'STALE')
        for _ in range(3):d=t.update(vision([40,40,20,20]),100,100,20)
        self.assertEqual(d['pointing_request'],dict(image_x=0.,image_y=0.))
        t.configure(dict(mode='person',enabled=False))
        self.assertEqual(t.update(vision(),100,100,20)['state'],'PAUSED')
        for bad in [dict(mode='unknown'),dict(enabled='yes'),dict(actuate=True)]:
            with self.assertRaises(ValueError):t.configure(bad)

    def test_far_target_is_new_identity(self):
        t=TargetTracker()
        a=t.update(vision([0,0,10,10]),100,100,10)
        b=t.update(vision([90,90,10,10]),100,100,10)
        self.assertGreater(b['track_id'],a['track_id']);self.assertEqual(b['consistent_frames'],1)

    def test_event_cooldown_and_maximum(self):
        with tempfile.TemporaryDirectory() as folder:
            e=EventStore(Path(folder));d=dict(motion_event=False,tags=[])
            with patch('events.time.monotonic',return_value=10):
                e.observe(d,dict(state='TRACKING'),b'raw',b'annotated','1',20)
            self.assertEqual(len(e.list()),1);self.assertEqual(e.image('event-0001'),b'annotated')
            with patch('events.time.monotonic',return_value=11):
                e.observe(d,dict(state='LOST'),b'raw',b'annotated','2',20)
            self.assertEqual(len(e.list()),1)
            with self.assertRaises(ValueError):e.image('../secrets')

if __name__=='__main__':unittest.main()
