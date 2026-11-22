"""One fixed short dual-gimbal trial, no vehicle motion or persistent writes."""
from pathlib import Path
import argparse,datetime,json,sys,time
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
import serial
from serial.tools import list_ports

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trial',choices=('yaw','pitch','both'),required=True)
    args=parser.parse_args();mode={'yaw':1,'pitch':2,'both':3}[args.trial]
    ports=[p for p in list_ports.comports() if p.vid==0x1A86]
    if len(ports)!=1:raise RuntimeError('Need one confirmed WCH serial port; no trial sent')
    out=root/'知行回路软件/build/r1_gimbal_probe'
    rec={'date':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
         'firmware':'r1_gimbal_probe','trial':args.trial,'mode':mode,
         'nonzero_motor_commands':'NONE','physical_observation':'PENDING_USER','samples':[],'commands':[]}
    trial_sent=False
    try:
        with serial.Serial(ports[0].device,115200,timeout=.08,write_timeout=.5) as link:
            link.reset_input_buffer()
            def read(command,prefix):
                link.write((command+'\n').encode('ascii'));end=time.monotonic()+1.5
                while time.monotonic()<end:
                    row=link.readline().decode('ascii',errors='replace').strip()
                    if row.startswith(prefix):
                        rec['commands'].append({'command':command,'reply':row});return row
                raise TimeoutError('No response to '+command)
            def state():
                values=[int(v) for v in read('GIMBAL_STATUS','GIMBAL,').split(',')[1:]]
                names=('ms','ready','active','mode','yaw_us','pitch_us','starts','stops','yaw_hz','pitch_hz')
                assert len(values)==len(names)
                return dict(zip(names,values))
            try:
                rec['ping']=read('PING','PONG');before=state();rec['before']=before
                assert before['ready']==1 and before['active']==0 and before['yaw_us']==0 and before['pitch_us']==0
                assert before['yaw_hz']==1000000 and before['pitch_hz']==1000000
                command={'yaw':'GIMBAL_YAW','pitch':'GIMBAL_PITCH','both':'GIMBAL_BOTH'}[args.trial]
                trial_sent=True;rec['start_reply']=read(command,'GIMBAL_STARTED')
                end=time.monotonic()+3.8
                while time.monotonic()<end:
                    s=state();rec['samples'].append(s)
                    assert s['ms']>=before['ms'],'MCU reset/clock discontinuity during trial'
                    assert s['ready']==1 and s['starts']==before['starts']+1
                    assert s['mode']==mode
                    assert s['yaw_us'] in (0,1400,1500,1600) and s['pitch_us'] in (0,1400,1500,1600)
                    if mode==1:assert s['pitch_us']==0,'Unrequested pitch PWM'
                    if mode==2:assert s['yaw_us']==0,'Unrequested yaw PWM'
                    if s['active']==0 and s['stops']==before['stops']+1:break
                    time.sleep(.1)
                else:raise TimeoutError('No automatic PWM stop observed')
                assert rec['samples'][-1]['yaw_us']==0 and rec['samples'][-1]['pitch_us']==0
                rec['automatic_pwm_stop']='PASS';rec['after_ping']=read('PING','PONG')
                rec['screens']={c:read(c,p) for c,p in [('OLED_SCREEN','SCREEN,'),('OLED2_SCREEN','SCREEN2,'),('OLED3_SCREEN','SCREEN3,')]}
                rec['result']='BOUNDED_GIMBAL_COMMAND_VERIFIED_PHYSICAL_PENDING'
            finally:
                if trial_sent:
                    try:rec['final_stop']=read('GIMBAL_STOP','GIMBAL_STOPPED')
                    except Exception as stop_error:rec['final_stop_error']=str(stop_error)
    except Exception as error:
        rec.update(result='TRIAL_FAILED',error=str(error));raise
    finally:
        name=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y%m%d-%H%M%S')+'-'+args.trial+'.json'
        out.mkdir(exist_ok=True)
        (out/name).write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(rec,ensure_ascii=False));print('Evidence:',out/name)

if __name__=='__main__':main()
