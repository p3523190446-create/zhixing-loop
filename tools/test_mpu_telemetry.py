"""Decode real raw captures and reject stale/mismatched/calibration-free data."""
from pathlib import Path
import copy,json,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'知行回路软件/debug_ui'))
from mpu_telemetry import decode_mpu,age_mpu
OUT=ROOT/'output/onboard_dashboard/mpu6050-20261025'
ref=json.loads((OUT/'flat-reference.json').read_text(encoding='utf-8'))
mapping=json.loads((OUT/'body-axis-mapping.json').read_text(encoding='utf-8'))
def row(folder):return json.loads((OUT/folder/'samples.json').read_text(encoding='utf-8'))['samples'][0]
def parse(r,reference=ref,axes=mapping):
    return decode_mpu(list(map(int,r['MPU_RAW'].split(',')[1:])),list(map(int,r['MPU_STATUS'].split(',')[1:])),reference,axes)
flat=parse(row('flat-20261025-040544'));front=parse(row('front-raised-20261025-040909'));left=parse(row('left-raised-20261025-041147'))
assert flat['valid'] and abs(flat['front_up_deg'])<.2 and abs(flat['left_up_deg'])<.2
assert front['valid'] and front['front_up_deg']>10 and abs(front['left_up_deg'])<1
assert left['valid'] and left['left_up_deg']>10 and abs(left['front_up_deg'])<1
assert front['nonstandard_identity'] and front['identity']==0x72
assert age_mpu(front,100,True)['valid']
for v in [age_mpu(front,1500,True),age_mpu(front,0,False)]:
    assert not v['valid'] and v['front_up_deg'] is None and v['left_up_deg'] is None and v['gyro_delta_raw'] is None
assert age_mpu(None,100,True) is None
bad=copy.deepcopy(ref);bad['who_am_i_hex']='0x68';assert not parse(row('front-raised-20261025-040909'),bad)['valid']
assert not parse(row('front-raised-20261025-040909'),None,None)['valid']
assert not parse(row('front-raised-20261025-040909'),{'bad':True},mapping)['valid']
r=row('front-raised-20261025-040909');parts=r['MPU_RAW'].split(',');parts[1]='250';r['MPU_RAW']=','.join(parts);assert not parse(r)['valid']
try:decode_mpu([1],[],ref,mapping)
except ValueError:pass
else:raise AssertionError('Malformed lengths accepted')
(OUT/'ui-decoder-verification.json').write_text(json.dumps(dict(result='PASS',scope='Actual flat/front/left captures; freshness, mismatch and missing reference rejection'),indent=2),encoding='utf-8')
print('PASS: real flat/front/left captures; aging/disconnect/mismatch/no-reference/malformed rejection')
