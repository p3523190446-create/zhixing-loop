"""Exercise isolated PC protocol with fake exchange; never open a serial port."""
from pathlib import Path
import importlib.util,json,sys,time,unittest
ROOT=Path(__file__).resolve().parents[2];SW=ROOT/'知行回路软件'
sys.path.insert(0,str(SW/'debug_ui_mecanum'))
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
original=load('original_pc_tests',Path(__file__).with_name('test_pc_speed_server.py'))
variant=load('mecanum_pc',SW/'debug_ui_mecanum/speed_server.py');original.module=variant
class Mecanum(original.Protocol):
    def setUp(self):
        super().setUp();self.b.identity='R1_DRIVE_STARTUP_MANUAL_MECANUM_V1_20261026'
    def test_full_forward_is250(self):
        self.b.command('set',self.vector());self.assertEqual(self.sent,['DRIVE_VECTOR,7,1,250,0,0'])
    def test_mixed_reverse_is_bounded(self):
        b=self.vector();b.update(throttle=-100,turn=100,strafe=100,limit=20)
        self.b.command('set',b);self.assertEqual(self.sent,['DRIVE_VECTOR,7,1,-16,16,16'])
    def test_strafe_is_separate_axis(self):
        b=self.vector();b.update(throttle=0,turn=0,strafe=-100,limit=20)
        self.b.command('set',b);self.assertEqual(self.sent,['DRIVE_VECTOR,7,1,0,-50,0'])
    def test_invalid_strafe_does_not_write(self):
        for x in (True,1.0,101,-101,'1'):
            b=self.vector();b['strafe']=x
            with self.assertRaises(ValueError):self.b.command('set',b)
        self.assertEqual(self.sent,[])
    def test_legacy_firmware_rejects_strafe(self):
        self.b.identity='R1_DRIVE_STARTUP_MANUAL_V8_20261023';b=self.vector();b['strafe']=10
        with self.assertRaises(ValueError):self.b.command('set',b)
        self.assertEqual(self.sent,[])
    def test_disconnected_state_does_not_advertise_mecanum(self):
        self.b.latest={'connected':False,'error':'fixture','sampled':time.monotonic()}
        self.assertFalse(self.b.state()['capabilities']['mecanum_control'])

if __name__=='__main__':
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(original.Protocol),unittest.defaultTestLoader.loadTestsFromTestCase(Mecanum)])
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    report={'result':'PASS' if result.wasSuccessful() else 'FAIL','cases':result.testsRun,'hardware_io':False}
    out=ROOT/'output/onboard_dashboard/mecanum-20261026/checks';out.mkdir(parents=True,exist_ok=True)
    (out/'pc-results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    sys.exit(0 if result.wasSuccessful() else 1)
