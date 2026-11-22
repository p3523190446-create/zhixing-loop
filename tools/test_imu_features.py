"""Protocol rejection and lifecycle checks; no serial or device actions."""
from pathlib import Path
import sys,json,zlib,py_compile
ROOT=Path(__file__).resolve().parents[2];UI=ROOT/'知行回路软件/debug_ui';sys.path.insert(0,str(UI))
from mpu_telemetry import decode_mpu,decode_features,age_mpu,FEATURE_METRICS
CAL=ROOT/'output/onboard_dashboard/mpu6050-20261025'
r=json.loads((CAL/'flat-reference.json').read_text(encoding='utf-8'));m=json.loads((CAL/'body-axis-mapping.json').read_text(encoding='utf-8'))
crc=zlib.crc32((CAL/'flat-reference.json').read_bytes()+(CAL/'body-axis-mapping.json').read_bytes())&0xffffffff
raw=[10,1,57,572,17402,3504,-1968,12,-128];status=[5000,1,1,105,114,1,1,100,0,0,10]
mpu=decode_mpu(raw,status,r,m);assert mpu['valid']
packet=[5000,10,1,67,1000,2000,3000,4000,12,24,300,1,2,3,2000,100,crc]
d=decode_features(packet,mpu,crc);assert d['valid'] and d['front_up_deg']==1 and d['features']['vibration_rms']==.012
for changed in ({16:crc+1},{1:250},{2:0},{3:195},{3:323}):
    q=packet[:]
    for i,v in changed.items():q[i]=v
    x=decode_features(q,mpu,crc);assert not x['valid'] and all(x['features'][k] is None for k in FEATURE_METRICS)
for q in (packet[:-1],packet+[0],[True]+packet[1:],packet[:8]+[-1]+packet[9:]):
    try:decode_features(q,mpu,crc)
    except ValueError:pass
    else:raise AssertionError('bad packet accepted')
for elapsed,connected in ((1500,True),(1,False)):
    x=age_mpu(d,elapsed,connected);assert not x['valid'] and not x['features']['valid'] and not x['features']['states']
    assert all(x['features'][k] is None for k in FEATURE_METRICS)
assert d['valid'] and d['features']['valid'],'aging must not mutate cached snapshot'
q=packet[:];q[3]=3;assert decode_features(q,mpu,crc)['features']['vibration_rms'] is None
q=packet[:];q[3]=513;assert 'freefall' in decode_features(q,mpu,crc)['features']['states']
zero=raw[:];zero[2:5]=[0,0,0];zero_mpu=decode_mpu(zero,status,r,m)
assert not zero_mpu['valid'] and decode_features(q,zero_mpu,crc)['valid'],'zero-g candidate must remain visible without raw gravity angle'
for name in ['mpu_telemetry.py','pc_integration.py','speed_server.py']:py_compile.compile(str(UI/name),doraise=True)
out=ROOT/'output/onboard_dashboard/imu-observer-20261025';out.mkdir(parents=True,exist_ok=True)
(out/'decoder-verification.json').write_text(json.dumps(dict(result='PASS',checks=['real-reference matching','feature scaling','CRC mismatch','source stale','sensor invalid','saturated/frozen','malformed packet','disconnect/aging clears metrics','cache unchanged','window not ready','freefall visible','backend syntax'],reference_crc32=crc),indent=2),encoding='utf-8')
print('PASS feature decoding, rejection, stale/disconnect clearing, backend syntax')
