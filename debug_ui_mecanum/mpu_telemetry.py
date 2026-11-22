"""Relative IMU display only. No device I/O, automatic compatibility or motion."""
import math

def decode_mpu(raw,status,reference,mapping):
    if len(raw)!=9 or len(status)!=11 or any(type(x) is not int for x in raw+status):
        raise ValueError('姿态数据长度或类型不符')
    if any(not -32768<=x<=32767 for x in raw[2:]) or raw[0]<0 or status[10]<0:
        raise ValueError('姿态数据范围不符')
    if any(status[i] not in (0,1) for i in (1,2,5,6)) or raw[1] not in (0,1):
        raise ValueError('姿态有效位不符')
    address,identity=status[3:5]
    try:
        matches=bool(reference and mapping and address==int(reference['address_hex'],16)==int(mapping['address_hex'],16)
            and identity==int(reference['who_am_i_hex'],16)==int(mapping['who_am_i_hex'],16)
            and len(reference['gyro_bias_raw'])==3 and all(math.isfinite(x) for x in reference['gyro_bias_raw'])
            and all(math.isfinite(reference[k]) for k in ('roll_reference_deg','pitch_reference_deg'))
            and mapping['front_up_sign'] in (-1,1) and mapping['left_up_sign'] in (-1,1))
    except (ValueError,TypeError,KeyError):matches=False
    valid=bool(matches and status[1] and status[2] and raw[1] and max(raw[0],status[10])<250)
    result=dict(valid=valid,source_valid=valid,age_ms=max(raw[0],status[10]),address=address,identity=identity,
        nonstandard_identity=identity!=0x68,reference_matches=matches,frames=status[7],errors=status[8],last_error=status[9],
        front_up_deg=None,left_up_deg=None,gyro_delta_raw=None,
        note='相对当前安装的水平参考；当前为兼容测试，精度待核。')
    if valid:
        ax,ay,az,_,gx,gy,gz=raw[2:]
        if ax*ax+ay*ay+az*az==0:result['valid']=False;return result
        roll=math.degrees(math.atan2(ay,az));pitch=math.degrees(math.atan2(-ax,math.hypot(ay,az)))
        wrap=lambda v:(v+180)%360-180
        result.update(front_up_deg=mapping['front_up_sign']*wrap(pitch-reference['pitch_reference_deg']),
            left_up_deg=mapping['left_up_sign']*wrap(roll-reference['roll_reference_deg']),
            gyro_delta_raw=[v-b for v,b in zip((gx,gy,gz),reference['gyro_bias_raw'])])
    return result

def age_mpu(value,elapsed_ms,connected):
    if value is None:return None
    value={**value,'age_ms':round(value['age_ms']+max(0,elapsed_ms))}
    value['valid']=bool(value['valid'] and connected and value['age_ms']<1500)
    if not value['valid']:value.update(front_up_deg=None,left_up_deg=None,gyro_delta_raw=None)
    if value.get('features'):
        f={**value['features']};f['age_ms']+=max(0,elapsed_ms)
        f['valid']=bool(f['valid'] and connected and f['age_ms']<1500)
        if not f['valid']:
            f.update({k:None for k in FEATURE_METRICS});f['states']=[]
        value['features']=f
    return value


FEATURE_FLAGS={1:'ready',2:'low_dynamic',4:'tilt',8:'extreme_tilt',16:'shock_recent',32:'rotating',64:'window_ready',128:'saturated',256:'frozen',512:'freefall',1024:'accelerating'}
FEATURE_METRICS=('front_up_deg','left_up_deg','turn_window_deg','yaw_rate_dps','vibration_rms','vibration_peak','jerk')

def decode_features(values,mpu,expected_crc):
    if len(values)!=17 or any(type(x) is not int for x in values):raise ValueError('IMU算法数据长度或类型不符')
    now,age,valid,flags,*_=values
    if not(0<=now<=0xffffffff and 0<=age<=0xffffffff and valid in (0,1) and 0<=flags<2048):raise ValueError('IMU算法状态不符')
    if any(not 0<=x<=0xffffffff for x in values[11:]):raise ValueError('IMU算法计数不符')
    if any(abs(x)>100000000 for x in values[4:11]) or any(x<0 for x in values[8:11]):raise ValueError('IMU算法量值不符')
    matches=expected_crc is not None and values[16]==expected_crc
    ok=bool(mpu.get('source_valid',mpu['valid']) and valid and flags&1 and not flags&(128|256) and age<250 and matches)
    f=dict(supported=True,valid=ok,age_ms=age,reference_matches=matches,reference_crc32=values[16],
           flags=flags,states=[name for bit,name in FEATURE_FLAGS.items() if flags&bit],
           shock_count=values[11],tilt_count=values[12],freefall_count=values[13],window_ms=values[14],frames=values[15],
           unit='relative_to_saved_gravity',sample_hz=20)
    f.update(zip(FEATURE_METRICS,[x/1000 if ok else None for x in values[4:11]]))
    if not flags&64:f.update(vibration_rms=None,vibration_peak=None)
    result={**mpu,'valid':ok,'features':f}
    if ok:result.update(front_up_deg=f['front_up_deg'],left_up_deg=f['left_up_deg'],attitude_source='mcu_complementary')
    else:result.update(valid=False,front_up_deg=None,left_up_deg=None)
    return result
