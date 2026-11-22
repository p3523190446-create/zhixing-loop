"""One explicit bounded servo trial; no motor, settings or parameter writes."""
from pathlib import Path
import argparse,datetime,json,sys,time
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
import serial
from serial.tools import list_ports

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trial',choices=('center','wiggle','wide'),required=True)
    parser.add_argument('--axis',choices=('horizontal','pitch'),default='horizontal')
    args=parser.parse_args()
    ports=[p for p in list_ports.comports() if p.vid==0x1A86]
    if len(ports)!=1:raise RuntimeError('Need one confirmed WCH serial port; no trial sent')
    out=root/'知行回路软件/build/r1_servo_probe'
    rec={'date':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
         'firmware':'r1_servo_probe','trial':args.trial,'axis':args.axis,'nonzero_motor_commands':'NONE',
         'physical_observation':'PENDING_USER','samples':[],'commands':[]}
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
                values=[int(v) for v in read('SERVO_STATUS','SERVO,').split(',')[1:]]
                names=('ms','ready','active','pulse_us','starts','stops','timer_hz')
                assert len(values)==len(names)
                return dict(zip(names,values))
            try:
                rec['ping']=read('PING','PONG');before=state();rec['before']=before
                assert before['ready']==1 and before['active']==0 and before['pulse_us']==0
                assert before['timer_hz']==1000000,'PWM clock not ready'
                # Exactly one explicit trial; fixed firmware deadline independent of serial.
                command={'center':'SERVO_CENTER','wiggle':'SERVO_WIGGLE','wide':'SERVO_WIDE'}[args.trial]
                trial_sent=True;rec['start_reply']=read(command,'SERVO_STARTED')
                end=time.monotonic()+(3.8 if args.trial=='wide' else 2.5)
                while time.monotonic()<end:
                    s=state();rec['samples'].append(s)
                    assert s['ms']>=before['ms'],'MCU reset or clock discontinuity during servo trial'
                    assert s['ready']==1 and s['starts']==before['starts']+1
                    allowed=(0,1300,1500,1700) if args.trial=='wide' else (0,1400,1500,1600)
                    assert s['pulse_us'] in allowed
                    if s['active']==0 and s['stops']==before['stops']+1:break
                    time.sleep(.1)
                else:raise TimeoutError('No automatic PWM stop seen')
                assert rec['samples'][-1]['pulse_us']==0
                rec['automatic_pwm_stop']='PASS'
                rec['after_ping']=read('PING','PONG')
                rec['screens']={c:read(c,p) for c,p in [('OLED_SCREEN','SCREEN,'),('OLED2_SCREEN','SCREEN2,'),('OLED3_SCREEN','SCREEN3,')]}
                rec['result']='COMMAND_AND_AUTO_PWM_STOP_VERIFIED_PHYSICAL_PENDING'
            finally:
                if trial_sent:
                    try:rec['final_stop']=read('SERVO_STOP','SERVO_STOPPED')
                    except Exception as stop_error:rec['final_stop_error']=str(stop_error)
    except Exception as error:
        rec.update(result='TRIAL_FAILED',error=str(error));raise
    finally:
        name=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y%m%d-%H%M%S')+'-'+args.axis+'-'+args.trial+'.json'
        out.mkdir(exist_ok=True)
        (out/name).write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(rec,ensure_ascii=False))
        print('Evidence:',out/name)

if __name__=='__main__':main()
