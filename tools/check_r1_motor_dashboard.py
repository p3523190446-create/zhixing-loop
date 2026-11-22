"""Read-only dashboard acceptance. Sends no nonzero motor commands or persistent writes."""
from pathlib import Path
import datetime, json, sys, time
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
import serial

def main(port='COM5'):
    out=ROOT/'知行回路软件/build/r1_motor_dashboard'
    stamp=datetime.datetime.now().astimezone()
    path=out/('dashboard-'+stamp.strftime('%Y%m%d-%H%M%S')+'.json')
    rec={'date':stamp.isoformat(),'firmware':'r1_motor_dashboard','nonzero_commands':'NONE',
         'scope':'PASSIVE_FEEDBACK_AND_THREE_OLED_TRANSPORT','physical_visual_acceptance':'PENDING_USER',
         'transcript':[],'samples':[]}
    try:
        with serial.Serial(port,115200,timeout=.1,write_timeout=1) as link:
            def query(cmd,prefix):
                link.write(cmd.encode('ascii')+b'\n');end=time.monotonic()+4
                while time.monotonic()<end:
                    row=link.readline().decode('ascii',errors='replace').strip()
                    if row:rec['transcript'].append({'command':cmd,'reply':row})
                    if row.startswith(prefix):return [int(x) for x in row.split(',')[1:]]
                raise TimeoutError(cmd)
            def snap():
                d=query('MOTOR_DASH_STATUS','MOTORDASH,')
                p=query('MOTOR_PULSE_STATUS','PULSE,');h=query('MOTOR_STATUS','MOTOR,')
                screens=[query(c,pr) for c,pr in [('OLED_SCREEN','SCREEN,'),('OLED2_SCREEN','SCREEN2,'),('OLED3_SCREEN','SCREEN3,')]]
                sample={'dashboard':d,'pulse':p,'uart':h,'screens':screens}
                rec['samples'].append(sample)
                assert len(d)==14 and d[2]==1 and d[4]==1,'Voltage/speed not fresh'
                assert 6000<=d[1]<=8500 and d[3]<=3000,'Voltage invalid'
                assert d[9]==0 and p[:2]==[0,0],'Unexpected motion command'
                assert d[10]==1 and d[11]==0 and d[12:14]==[1,1],'Not stationary monitor state'
                assert all(abs(x)<=5 for x in d[5:9]),'Feedback is not stationary'
                assert h[1:3]==[0,0],'UART errors/drops'
                assert all(x[1:]==[1,0] for x in screens),'OLED transfer error'
                return sample
            first=snap();print('Dashboard fresh, stationary, three OLEDs updating.',flush=True)
            # Cover the former 60s bench-upload lease once, without motor actions.
            end=time.monotonic()+80
            while True:
                time.sleep(3)
                last=snap()
                if last['dashboard'][0]>=70000 and len(rec['samples'])>=3:break
                if time.monotonic()>end:raise TimeoutError('70s monitor boundary not reached')
            for i in range(3):assert last['screens'][i][0]>first['screens'][i][0]
            assert last['uart'][0]>first['uart'][0]
            rec['result']='PASS_FRESH_BATTERY_FOUR_SPEEDS_THREE_OLEDS_NO_MOTION'
            rec['battery_mv']=last['dashboard'][1];rec['four_speeds_mm_s']=last['dashboard'][5:9]
            rec['monitor_beyond_60s']='PASS'
            print(json.dumps({k:rec[k] for k in ('result','battery_mv','four_speeds_mm_s','monitor_beyond_60s')},ensure_ascii=False),flush=True)
    except BaseException as e:
        rec['result']='STOPPED_EARLY';rec['error']=str(e);raise
    finally:
        path.write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('Evidence:',path,flush=True)
if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else 'COM5')
