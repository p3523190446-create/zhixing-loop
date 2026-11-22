"""Read preflight or run four fixed 250 ms suspended pulses after human setup confirmation.
No driver parameter writes, resets or firmware installs. Never retry ambiguous motion.
"""
from pathlib import Path
import sys, json, time, datetime
sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
import serial
root=Path(__file__).resolve().parents[2]
out=root/'知行回路软件/build/motor_rewired_checks'
out.mkdir(exist_ok=True)
run='--run-suspended' in sys.argv
monitor='--enable-monitor' in sys.argv
channel_arg=next((a.split('=',1)[1] for a in sys.argv[1:] if a.startswith('--channels=')),'1,2,3,4')
channels=[int(c) for c in channel_arg.split(',')]
assert channels and len(set(channels))==len(channels) and all(1<=c<=4 for c in channels)
stamp=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
path=out/(stamp.strftime('%Y%m%d-%H%M%S')+('-pulses.json' if run else '-preflight.json'))
rec={'date':stamp.isoformat(),'mode':'SUSPENDED_PULSES' if run else 'MONITOR_PREFLIGHT' if monitor else 'READ_ONLY',
     'firmware':'r1_motor_dashboard_no_knob','physical_observation':'PENDING_USER',
     'driver_parameter_writes':'NONE','transcript':[],'records':[]}
try:
    with serial.Serial('COM5',115200,timeout=.1,write_timeout=1) as link:
        def query(cmd,prefix):
            link.write((cmd+'\n').encode('ascii'))
            end=time.monotonic()+3
            while time.monotonic()<end:
                line=link.readline().decode('ascii',errors='replace').strip()
                if line:rec['transcript'].append({'command':cmd,'reply':line})
                if line.startswith(prefix):return line
            raise TimeoutError('No response: '+cmd)
        def values(cmd,prefix):return [int(v) for v in query(cmd,prefix).split(',')[1:]]
        def snapshot(require_stopped=True):
            s={'dashboard':values('MOTOR_DASH_STATUS','MOTORDASH,'),
               'pulse':values('MOTOR_PULSE_STATUS','PULSE,'),
               'uart':values('MOTOR_STATUS','MOTOR,'),
               'live':values('MOTOR_LIVE_STATUS','MOTORLIVE,')}
            rec['records'].append(s)
            d,p,u=s['dashboard'],s['pulse'],s['uart']
            assert len(d)==14 and d[2]==1 and d[4]==1,'Battery/speed feedback not fresh'
            assert 6000<=d[1]<=8500,'Battery voltage outside tested range'
            assert p[0]==0 and d[9]==0,'Unexpected active motion'
            if require_stopped:assert all(abs(v)<=5 for v in d[5:9]),'Wheel speed feedback not stopped'
            assert u[1:3]==[0,0],'Motor UART errors or drops'
            assert d[11]==0 and d[12:14]==[1,1],'Motor fault or monitoring disabled'
            return s
        if monitor:
            # Transient feedback upload only; no persistent parameters or drive command.
            for attempt in range(4):
                ack=query('MOTOR_MONITOR_ON','MONITOR_')
                if ack=='MONITOR_QUEUED':break
                assert ack=='MONITOR_BUSY',ack
                time.sleep(.15)
            else:raise RuntimeError('Feedback monitor remains busy')
            rec['monitor_ack']=ack
            time.sleep(.7)
        before=snapshot()
        print('PRECHECK_OK battery_mv='+str(before['dashboard'][1])+' speeds='+str(before['dashboard'][5:9]),flush=True)
        if run:
            try:
                for index,channel in enumerate(channels):
                    if index:time.sleep(3.3)
                    before=snapshot()
                    print('M'+str(channel)+' short pulse in 3 seconds',flush=True)
                    time.sleep(3)
                    # Require fresh voltage/feedback immediately before every motion request.
                    before=snapshot()
                    ack=query('MOTOR_TEST_M'+str(channel),'MOTOR_TEST_')
                    assert ack=='MOTOR_TEST_STARTED,M'+str(channel),ack
                    print(ack,flush=True)
                    time.sleep(.8)
                    # Require stop frames and stopped feedback before the next wheel.
                    end=time.monotonic()+3
                    stable=0
                    while True:
                        after=snapshot(require_stopped=False)
                        if all(abs(v)<=5 for v in after['dashboard'][5:9]):stable+=1
                        else:stable=0
                        if stable>=2:break
                        if time.monotonic()>=end:raise RuntimeError('Wheel feedback did not settle within 3 seconds; disconnect battery')
                        time.sleep(.15)
                    p0,p1=before['pulse'],after['pulse']
                    assert p1[1]==p0[1]+1 and p1[2]>=p0[2]+3 and p1[5]==channel,'Stop frame accounting mismatch'
                    after['channel_completed']=channel
                    after['stop_frame_elapsed_ms']=(p1[4]-p1[3])&0xffffffff
                    assert after['stop_frame_elapsed_ms']<1000,'Stop frames delayed'
                    print('M'+str(channel)+' zero-PWM sent; feedback stopped',flush=True)
                rec['result']='REQUESTED_PULSES_COMMAND_AND_STOPPED_FEEDBACK_PASS'
                rec['channels_completed']=channels
            finally:
                try:rec['final_stop_ack']=query('MOTOR_STOP','MOTOR_STOP_')
                except Exception as stop_error:rec['final_stop_error']=str(stop_error)
        else:
            time.sleep(.7)
            snapshot()
            rec['result']='PREFLIGHT_FRESH_FEEDBACK_PASS'
except Exception as e:
    rec['result']='STOPPED';rec['error']=str(e)
finally:
    path.write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'result':rec['result'],'error':rec.get('error'),'evidence':str(path)},ensure_ascii=False),flush=True)
