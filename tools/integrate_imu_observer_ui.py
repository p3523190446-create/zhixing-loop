"""One-time, guarded integration; keeps the existing sensor design and serial owner."""
from pathlib import Path
import hashlib
ROOT=Path(__file__).resolve().parents[2];UI=ROOT/'知行回路软件/debug_ui'
def edit(name,old,new):
    p=UI/name;s=p.read_text(encoding='utf-8')
    assert s.count(old)==1,(name,s.count(old));p.write_text(s.replace(old,new),encoding='utf-8')
def main():
    shared=Path(r'C:\Users\panyuanhao\AI共享记忆\共享共识.md')
    assert hashlib.sha256(shared.read_bytes()).hexdigest()=='176ff6269b61e6c40c9c2fb8de74e487e721623ab2c18b208a78093a96f04644','Reread new shared records'
    edit('mpu_telemetry.py','    return value\n', '''    if value.get('features'):
        f={**value['features']};f['age_ms']+=max(0,elapsed_ms)
        f['valid']=bool(f['valid'] and connected and f['age_ms']<1500)
        if not f['valid']:
            f.update({k:None for k in FEATURE_METRICS});f['states']=[]
        value['features']=f
    return value
''')
    p=UI/'mpu_telemetry.py'
    with p.open('a',encoding='utf-8') as f:f.write('''

FEATURE_FLAGS={1:'ready',2:'low_dynamic',4:'tilt',8:'extreme_tilt',16:'shock_recent',32:'rotating',64:'window_ready',128:'saturated',256:'frozen',512:'freefall',1024:'accelerating'}
FEATURE_METRICS=('front_up_deg','left_up_deg','turn_window_deg','yaw_rate_dps','vibration_rms','vibration_peak','jerk')

def decode_features(values,mpu,expected_crc):
    if len(values)!=17 or any(type(x) is not int for x in values):raise ValueError('IMU算法数据长度或类型不符')
    now,age,valid,flags,*_=values
    if not(0<=now<=0xffffffff and 0<=age<=0xffffffff and valid in (0,1) and 0<=flags<2048):raise ValueError('IMU算法状态不符')
    if any(not 0<=x<=0xffffffff for x in values[11:]):raise ValueError('IMU算法计数不符')
    if any(abs(x)>100000000 for x in values[4:11]) or any(x<0 for x in values[8:11]):raise ValueError('IMU算法量值不符')
    matches=expected_crc is not None and values[16]==expected_crc
    ok=bool(mpu['valid'] and valid and flags&1 and not flags&(128|256) and age<250 and matches)
    f=dict(supported=True,valid=ok,age_ms=age,reference_matches=matches,reference_crc32=values[16],
           flags=flags,states=[name for bit,name in FEATURE_FLAGS.items() if flags&bit],
           shock_count=values[11],tilt_count=values[12],freefall_count=values[13],window_ms=values[14],frames=values[15],
           unit='relative_to_saved_gravity',sample_hz=20)
    f.update(zip(FEATURE_METRICS,[x/1000 if ok else None for x in values[4:11]]))
    if not flags&64:f.update(vibration_rms=None,vibration_peak=None)
    result={**mpu,'features':f}
    if ok:result.update(front_up_deg=f['front_up_deg'],left_up_deg=f['left_up_deg'],attitude_source='mcu_complementary')
    else:result.update(valid=False,front_up_deg=None,left_up_deg=None)
    return result
''')
    edit('pc_integration.py','from mpu_telemetry import decode_mpu,age_mpu','from mpu_telemetry import decode_mpu,age_mpu,decode_features\nimport zlib')
    edit('pc_integration.py',"        self.photos=folder/'photos'", "        try:self.mpu_crc=zlib.crc32((calibration/'flat-reference.json').read_bytes()+(calibration/'body-axis-mapping.json').read_bytes())&0xffffffff\n        except OSError:self.mpu_crc=None\n        self.photos=folder/'photos'")
    edit('pc_integration.py',"                self.mpu_failures=0;bench.log('mpu_readonly_snapshot',data=self.mpu)","                if getattr(bench,'imu_observer_supported',False):\n                    self.mpu=decode_features(bench.numbers('MPU_FEATURES','MPU_FEATURES,',17),self.mpu,self.mpu_crc)\n                self.mpu_failures=0;bench.log('mpu_readonly_snapshot',data=self.mpu)")
    edit('speed_server.py','        self.mpu_supported = False','        self.mpu_supported = False\n        self.imu_observer_supported = False')
    edit('speed_server.py','                        self.control_verified = not self.identity',"                        self.imu_observer_supported=False\n                        if self.mpu_supported:\n                            try:self.imu_observer_supported=self.exchange('MPU_FEATURES_ID','MPU_FEATURES_ID,')=='MPU_FEATURES_ID,IMU_OBSERVER_V1_20HZ'\n                            except (TimeoutError,ValueError):pass\n                        self.control_verified = not self.identity")
    # Only the disconnect reset has this exact surrounding indentation.
    edit('speed_server.py','                    self.mpu_supported=False\n                    self.latest', '                    self.mpu_supported=False\n                    self.imu_observer_supported=False\n                    self.latest')
    print('Read-only feature protocol integrated')
if __name__=='__main__':main()
