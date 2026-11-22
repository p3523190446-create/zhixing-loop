"""Real PC broker/session recovery code with fake serial; never opens hardware."""
from pathlib import Path
import sys,tempfile,time,unittest,threading
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'知行回路软件/debug_ui'))
from pc_integration import Integration
from gimbal_controls import Controls,Request

G=dict(ms=1000,ready=1,active=0,mode=5,yaw_us=0,pitch_us=0,starts=4,stops=4)
class Recovery(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name);self.c=Controls(self.folder)
    def tearDown(self):self.tmp.cleanup()
    def test_first_error_survives_missing_device_retries(self):
        self.c.owner='old-owner';self.c.state='MANUAL'
        self.c.disconnect('Write timeout');self.c.disconnect('P9 absent')
        self.assertEqual(self.c.public()['error'],'Write timeout')
        self.assertEqual(len(self.c.public()['events']),1)
        self.assertIsNone(self.c.owner)
    def test_readonly_recovery_requires_confirmed_zero(self):
        self.c.disconnect('WriteFile failed')
        self.c.observe_link(dict(G,active=1,yaw_us=1500,pitch_us=1500))
        self.assertEqual(self.c.public()['state'],'OFFLINE')
        self.c.observe_link(G)
        self.assertEqual(self.c.public()['state'],'STOPPED')
        self.assertIsNone(self.c.owner);self.assertIsNone(self.c.last_touch or None)
        self.assertEqual(self.c.public()['last_failure']['error'],'WriteFile failed')
        self.assertIsNone(self.c.public()['error'])
    def test_busy_start_rejection_does_not_break_shared_serial(self):
        r=Request('start',{},time.monotonic()+1)
        self.c.queue.put((1,0,r));sent=[]
        self.c.service(lambda command,prefix:sent.append(command),lambda:dict(G,active=1))
        self.assertTrue(r.done.is_set());self.assertEqual(r.code,409);self.assertEqual(sent,[])
    def test_sensor_cycle_is_invalidated_on_disconnect(self):
        i=Integration(self.folder);i.rows={'STATUS':[1]};i.at=6;i.sampled=time.monotonic();i.telemetry={'connected':True};i.gimbal=G
        i.disconnect('USB lost')
        self.assertEqual(i.rows,{});self.assertEqual(i.at,0);self.assertEqual(i.sampled,0);self.assertIsNone(i.gimbal)
    def test_stop_confirmation_callback_does_not_reenter_broker_lock(self):
        i=Integration(self.folder)
        r=Request('stop',{},time.monotonic()+1);i.controls.queue.put((0,0,r))
        class Fake:
            def exchange(self,command,prefix):return prefix
            def numbers(self,command,prefix,count):return list(G.values())+[1000000,1000000]
        fake=Fake()
        thread=threading.Thread(target=lambda:i.controls.service(fake.exchange,lambda:i.gimbal_snapshot(fake)),daemon=True)
        thread.start();thread.join(.5)
        self.assertFalse(thread.is_alive(),'stop callback deadlocked shared serial owner')
        self.assertTrue(r.done.is_set());self.assertTrue(r.response['stopped'])
    def test_old_sensor_group_does_not_overwrite_fresh_control_snapshot(self):
        i=Integration(self.folder);i.at=7;i.diagnostics_at=time.monotonic()
        old=dict(G,active=0);fresh=dict(G,ms=2000,active=1,yaw_us=1500,pitch_us=1500)
        i.gimbal=fresh
        i.rows={'STATUS':[1000,1,0,0,160,0,0,0,0,0,0], 'MOTOR_DASH_STATUS':[1000,7700,1,0,1,0,0,0,0,0,1,0,0,0],
                'RECOVERY_STATUS':[0]*9,'PARAM_STATUS':[120,0,0,0],'MUTE_STATUS':[0]*5,'MOTOR_STATUS':[0]*7,'GIMBAL_STATUS':list(old.values())+[1000000,1000000]}
        class Fake:
            def exchange(self,*args):raise AssertionError('No writes expected')
            def numbers(self,command,prefix,count):return [1000,1,1,120,0,0,0,0,0,0,10,0]
        i.poll(Fake());self.assertEqual(i.gimbal,fresh)

if __name__=='__main__':unittest.main()
