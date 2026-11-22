"""MPU/legacy telemetry; optional explicit volatile compatibility trial, never motion."""
from pathlib import Path
import argparse,datetime,json,math,sys,time
sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
import serial
def decode_raw(line):
    values=list(map(int,line.split(',')[1:]));assert len(values)==9
    age,valid,*raw=values
    assert valid in (0,1) and all(-32768<=x<=32767 for x in raw)
    result=dict(age_ms=age,valid=bool(valid),raw=raw)
    if valid:
        ax,ay,az,t,gx,gy,gz=raw
        result.update(accel_g=[round(x/16384,6) for x in (ax,ay,az)],gyro_dps=[round(x/131,5) for x in (gx,gy,gz)],
            sensor_temperature_c=round(t/340+36.53,2),accel_norm_g=round(math.sqrt(ax*ax+ay*ay+az*az)/16384,5),
            uncalibrated_roll_deg=round(math.degrees(math.atan2(ay,az)),3),
            uncalibrated_pitch_deg=round(math.degrees(math.atan2(-ax,math.hypot(ay,az))),3))
    return result
def main():
    p=argparse.ArgumentParser();p.add_argument('--port',default='COM5');p.add_argument('--seconds',type=float,default=6)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--compat-trial',action='store_true')
    a=p.parse_args();assert 1<=a.seconds<=30
    result=dict(recorded_at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        scope=('Explicit volatile ID0x72 register-compatibility trial; no motion or calibration commands' if a.compat_trial else
               'Read-only P9 static telemetry; raw tilt uncalibrated, not road roughness acceptance'),samples=[])
    s=serial.Serial();s.port=a.port;s.baudrate=115200;s.timeout=.08;s.write_timeout=1;s.dtr=False;s.rts=False
    def query(command,prefix=None):
        prefix=prefix or command+',';s.write((command+'\n').encode('ascii'));s.flush();end=time.monotonic()+1.2
        while time.monotonic()<end:
            line=s.readline().decode('ascii',errors='replace').strip()
            if line.startswith(prefix):return line
            if line.startswith('ERR'):raise RuntimeError(command+': '+line)
        raise TimeoutError(command)
    try:
        s.open()
        with s:
            s.reset_input_buffer();result['identity']=query('MPU_ID')
            assert result['identity']=='MPU_ID,MPU6050_PD6_PD7_ADDR69_V1'
            result['drive_identity']=query('DRIVE_ID');result['line_identity']=query('LINE_ID')
            if a.compat_trial:
                result['diag_before']=query('MPU_DIAG')
                diag=list(map(int,result['diag_before'].split(',')[1:]))
                assert len(diag)==9 and diag[:3]==[1,0x72,0x72],result['diag_before']
                assert diag[3:8]==[0x40,0,0,0,0], 'Unexpected reset-state register map; no trial writes'
                result['explicit_compat_trial_command']=query('MPU_COMPAT_ON')
                assert result['explicit_compat_trial_command']=='MPU_COMPAT_ON,TRIAL_ID72'
                time.sleep(1.3);result['diag_after']=query('MPU_DIAG')
                result['identity_warning']='WHO_AM_I 0x72, unknown silicon; register-compatibility trial only'
            started=time.monotonic()
            while time.monotonic()-started<a.seconds:
                item={'elapsed_s':round(time.monotonic()-started,3)}
                for command,prefix in [('MPU_STATUS',None),('MPU_RAW',None),('DRIVE_STATUS','DRIVE,'),('GIMBAL_STATUS','GIMBAL,'),('LINE_STATUS',None)]:
                    item[command]=query(command,prefix)
                item['mpu']=decode_raw(item['MPU_RAW'])
                if a.compat_trial:item['mpu']['identity_warning']='0x72 compatibility trial; uncalibrated and not used for motion'
                drive=list(map(int,item['DRIVE_STATUS'].split(',')[1:]));gimbal=list(map(int,item['GIMBAL_STATUS'].split(',')[1:]))
                assert len(drive)==9 and drive[1:5]==[0,0,0,0],item['DRIVE_STATUS']
                assert len(gimbal)==10 and gimbal[2]==0 and gimbal[4:6]==[0,0],item['GIMBAL_STATUS']
                result['samples'].append(item);time.sleep(.2)
    except Exception as e:result['error']=str(e)
    finally:
        a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(identity=result.get('identity'),count=len(result['samples']),first=result['samples'][:1],last=result['samples'][-1:],error=result.get('error')),ensure_ascii=False,indent=2))
    if result.get('error'):raise SystemExit(1)
if __name__=='__main__':main()
