"""One bounded suspended calibration. Does not change driver persistent settings."""
from pathlib import Path
import argparse,datetime,json,math,sys,time
ROOT=Path(__file__).resolve().parents[2]
PWM_LEVELS=[150,200,250,300]

def run(channel,level,stage):
    sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
    import serial
    out=ROOT/'知行回路软件/build'/stage
    stamp=datetime.datetime.now().astimezone()
    path=out/('cal-'+stamp.strftime('%Y%m%d-%H%M%S-%f')+f'-M{channel}-P{PWM_LEVELS[level-1]}.json')
    r={'recorded_at':stamp.isoformat(),'channel':channel,'pwm':PWM_LEVELS[level-1],
       'kick_pwm':350,'kick_threshold_ms':250,'scope':'SUSPENDED_ONLY','result':'NOT_RUN','samples':[],'transcript':[]}
    with serial.Serial('COM5',115200,timeout=.1,write_timeout=1) as link:
        def query(command,prefix):
            link.write(command.encode()+b'\n');deadline=time.monotonic()+4
            while time.monotonic()<deadline:
                row=link.readline().decode('ascii',errors='replace').strip()
                if row:r['transcript'].append({'command':command,'reply':row})
                if row.startswith(prefix):return row
            raise TimeoutError(command+'; no ambiguous motion retry')
        def values(command,prefix):return [int(v) for v in query(command,prefix).split(',')[1:]]
        def upload(enable):
            for _ in range(30):
                ack=query('MOTOR_ENCODER_ON' if enable else 'MOTOR_ENCODER_OFF','ENCODER_UPLOAD_')
                if ack=='ENCODER_UPLOAD_QUEUED':return
                if ack!='ENCODER_UPLOAD_BUSY':raise RuntimeError(ack)
                time.sleep(.1)
            raise RuntimeError('Upload busy')
        def require(condition,message):
            if not condition:raise RuntimeError(message)
        try:
            pbefore=values('MOTOR_PULSE_STATUS','PULSE,');require(pbefore[0]==0,'Motion already active')
            upload(True);time.sleep(3.5)
            before=values('MOTOR_LIVE_STATUS','MOTORLIVE,')
            require(len(before)==17 and max(before[1:3])<250,'Feedback not fresh')
            require(all(abs(v)<20 for v in before[7:11]),'Wheel already moving')
            time.sleep(.4);baseline=values('MOTOR_LIVE_STATUS','MOTORLIVE,')
            require(before[3:7]==baseline[3:7],'Stationary encoder counts changing')
            r['before']=baseline
            for _ in range(20):
                ack=query(f'MOTOR_START_M{channel}_{level}','MOTOR_START_')
                if ack==f'MOTOR_START_STARTED,M{channel},L{level}':break
                require(ack=='MOTOR_START_BUSY_OR_OFFLINE',ack);time.sleep(.1)
            else:raise RuntimeError('Start unavailable')
            deadline=time.monotonic()+3.5
            while time.monotonic()<deadline:
                live=values('MOTOR_LIVE_STATUS','MOTORLIVE,');r['samples'].append(live)
                require(len(live)==17,'Malformed telemetry')
                if not live[13]:break
                require(max(live[1:3])<250,'Stale feedback')
                time.sleep(.15)
            else:raise RuntimeError('Calibration deadline exceeded')
            time.sleep(.6)
            pafter=values('MOTOR_PULSE_STATUS','PULSE,')
            speed=values('MOTOR_SPEED_STATUS','SPEED,')
            window=values('MOTOR_SPEED_WINDOW','SPEEDWINDOW,')
            after=values('MOTOR_ENCODER_STATUS','ENCODER,')
            fault=values('MOTOR_FAULT_STATUS','MOTORFAULT,')
            h=values('MOTOR_STATUS','MOTOR,')
            r.update({'pulse_before':pbefore,'pulse_after':pafter,'speed':speed,'window':window,
                      'after':after,'fault':fault,'health':h})
            require(pafter[0]==0 and pafter[1]==pbefore[1]+1 and pafter[2]==pbefore[2]+3,
                    'Stop frames incomplete')
            require(speed[7]==0,'Protection stopped trial')
            require(h[1]==0 and h[2]==0,'UART errors/drops')
            time.sleep(.5);settled=values('MOTOR_ENCODER_STATUS','ENCODER,');r['settled']=settled
            require(after[2:6]==settled[2:6],'Counts changing after stop')
            delta=[after[i+2]-baseline[i+3] for i in range(4)];r['delta']=delta
            require(delta[channel-1]>=0 and all(delta[i]==0 for i in range(4) if i!=channel-1),
                    'Other channel or negative counts changed')
            require(speed[8]>=5 and window[3]-window[2]>=300,'Incomplete sample window')
            average=(window[1]-window[0])*math.pi*65/2340*1000/(window[3]-window[2])
            r.update({'encoder_average_mm_s':average,'reported_average_mm_s':speed[9]/speed[8],
                      'reported_min_max_mm_s':speed[10:12],'result':'MEASURED'})
        except BaseException as exc:
            r['error']=str(exc);r['result']='STOPPED_EARLY'
            try:r['stop_request']=query('MOTOR_STOP','MOTOR_STOP_')
            except Exception as stop_exc:r['stop_error']=str(stop_exc)
            raise
        finally:
            try:
                time.sleep(.6);upload(False);time.sleep(.4)
                r['final_pulse']=query('MOTOR_PULSE_STATUS','PULSE,')
                r['final_encoder']=query('MOTOR_ENCODER_STATUS','ENCODER,')
            except Exception as exc:r['cleanup_error']=str(exc)
            path.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({'evidence':str(path),'result':r['result'],
                'channel':channel,'pwm':r['pwm'],'encoder_average_mm_s':r.get('encoder_average_mm_s'),
                'range':r.get('reported_min_max_mm_s'),'error':r.get('error')},ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--channel',type=int,choices=range(1,5),required=True)
    p.add_argument('--level',type=int,choices=range(1,5),required=True)
    p.add_argument('--stage',choices=['r1_motor_startup_hold'],default='r1_motor_startup_hold')
    p.add_argument('--execute',action='store_true')
    a=p.parse_args()
    if a.execute:run(a.channel,a.level,a.stage)
    else:print('Prepared only; no device access.')
