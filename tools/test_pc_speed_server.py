"""Protocol/boundary checks use a fake exchange, never a serial port."""
import importlib.util, pathlib, tempfile, time, unittest
source=pathlib.Path(__file__).resolve().parents[1]/'debug_ui/speed_server.py'
spec=importlib.util.spec_from_file_location('pc_speed',source)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class Protocol(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.b=module.Bench(pathlib.Path(self.tmp.name))
        self.b.link=object();self.b.owner='owner';self.b.generation=7;self.b.touched=time.monotonic()
        self.b.control_verified=True
        self.b.latest={'connected':True,'sampled':time.monotonic(),'drive':{'active':True},'motor_active':False}
        self.sent=[]
        def exchange(command,prefix):
            self.sent.append(command)
            return prefix
        self.b.exchange=exchange
    def tearDown(self):self.b.raw.close();self.tmp.cleanup()
    def vector(self,**values):
        return dict(session='owner',seq=1,throttle=100,turn=0,limit=100,**values)
    def test_full_forward_is250(self):
        self.b.command('set',self.vector());self.assertEqual(self.sent,['DRIVE_SET,7,1,250,250'])
    def test_mixed_reverse_is_bounded(self):
        body=self.vector();body.update(throttle=-100,turn=100)
        self.b.command('set',body);self.assertEqual(self.sent,['DRIVE_SET,7,1,0,-250'])
    def test_old_sequence_never_writes(self):
        self.b.seq=4
        with self.assertRaises(ValueError):self.b.command('set',self.vector())
        self.assertEqual(self.sent,[])
    def test_out_of_range_and_boolean_never_write(self):
        for field,value in [('limit',101),('throttle',-101),('seq',True),('limit',100.0)]:
            body=self.vector();body[field]=value
            with self.assertRaises(ValueError):self.b.command('set',body)
        self.assertEqual(self.sent,[])
    def test_no_owner_never_writes(self):
        self.b.owner=None
        with self.assertRaises(ValueError):self.b.command('set',self.vector())
        self.assertEqual(self.sent,[])
    def test_stale_telemetry_never_writes(self):
        self.b.latest['sampled']-=2
        with self.assertRaises(ValueError):self.b.command('set',self.vector())
        self.assertEqual(self.sent,[])
    def test_bench_requires_true_confirmation(self):
        for confirm in [False,1,'true',None]:
            with self.assertRaises(ValueError):self.b.command('run',{'channel':1,'bench_confirmed':confirm})
        self.assertEqual(self.sent,[])
    def test_brake_uses_fresh_seq(self):
        self.b.command('brake',{'session':'owner','seq':2})
        self.assertEqual(self.sent,['DRIVE_BRAKE,7,2']);self.assertEqual(self.b.seq,2)
        with self.assertRaises(ValueError):self.b.command('set',self.vector())
        self.assertEqual(len(self.sent),1)
    def test_expired_owner_stops(self):
        self.b.touched-=1
        stopped=[]
        self.b.stop=lambda:stopped.append(True)
        with self.assertRaises(ValueError):self.b.command('set',self.vector())
        self.assertTrue(stopped);self.assertEqual(self.sent,[])

if __name__=='__main__':unittest.main()
