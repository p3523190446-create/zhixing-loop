"""Explicit RAM compatibility trial and passive observer capture; no motion writes."""
from pathlib import Path
import sys,time,json,datetime,argparse
sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
import serial
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=dict(started_at=datetime.datetime.now().isoformat(),scope='static live telemetry only; events not physically exercised',samples=[])
    s=serial.Serial();s.port='COM5';s.baudrate=115200;s.timeout=.08;s.write_timeout=1;s.dtr=False;s.rts=False
    def query(cmd,prefix=None):
        s.write((cmd+'\n').encode());s.flush();end=time.monotonic()+1.5
        while time.monotonic()<end:
            line=s.readline().decode('ascii',errors='replace').strip()
            if line.startswith(prefix or cmd+','):return line
            if line.startswith('ERR'):raise RuntimeError(line)
        raise TimeoutError(cmd)
    def numbers(cmd,prefix=None):return list(map(int,query(cmd,prefix).split(',')[1:]))
    try:
        s.open()
        with s:
            s.reset_input_buffer();result['feature_id']=query('MPU_FEATURES_ID')
            assert result['feature_id']=='MPU_FEATURES_ID,IMU_OBSERVER_V1_20HZ'
            d=numbers('MPU_DIAG');result['diag_before']=d
            assert len(d)==9 and d[:3]==[1,114,114] and d[8]==0,d
            assert d[3:8] in ([64,0,0,0,0],[1,19,3,0,0],[1,19,6,0,0]),'Unknown configuration; no compatibility trial'
            result['compatibility']=query('MPU_COMPAT_ON');assert result['compatibility']=='MPU_COMPAT_ON,TRIAL_ID72'
            time.sleep(1.3);result['diag_after']=numbers('MPU_DIAG')
            assert result['diag_after']==[1,114,114,1,19,6,0,0,1],result['diag_after']
            start=time.monotonic()
            while time.monotonic()-start<9:
                row=dict(elapsed=round(time.monotonic()-start,3))
                for cmd,prefix in [('MPU_STATUS',None),('MPU_RAW',None),('MPU_FEATURES',None),('DRIVE_STATUS','DRIVE,'),('GIMBAL_STATUS','GIMBAL,'),('LINE_STATUS',None)]:row[cmd]=numbers(cmd,prefix)
                assert len(row['MPU_STATUS'])==11 and row['MPU_STATUS'][1:5]==[1,1,105,114]
                assert row['DRIVE_STATUS'][1:5]==[0,0,0,0] and row['GIMBAL_STATUS'][2]==0 and row['GIMBAL_STATUS'][4:6]==[0,0]
                f=row['MPU_FEATURES'];assert len(f)==17 and f[1]<250 and f[2]==1 and f[16]==2529589088
                result['samples'].append(row);time.sleep(.18)
            assert result['samples'][-1]['MPU_FEATURES'][3]&64,'Window never became ready'
            result['result']='PASS'
    except Exception as e:result['error']=str(e)
    finally:
        a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(result=result.get('result'),count=len(result['samples']),diag_before=result.get('diag_before'),diag_after=result.get('diag_after'),last=result['samples'][-1:] ,error=result.get('error')),ensure_ascii=False))
    if result.get('error'):raise SystemExit(1)
if __name__=='__main__':main()
