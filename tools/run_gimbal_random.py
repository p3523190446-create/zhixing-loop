"""Explicit continuous two-axis run with heartbeat and stop-file; never controls car motors.
Each launch sends RUN once. Lost connection/reboot never automatically reconnects or rearms.
"""
from pathlib import Path
import datetime,json,os,sys,time
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
import serial
from serial.tools import list_ports
out=root/'知行回路软件/build/r1_gimbal_continuous';out.mkdir(exist_ok=True)
stop_file=out/'stop-request.flag'
live=out/'live-status.json'
journal=out/'run-journal.jsonl'
stamp=lambda:datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
def write_live(data):
    data['updated_at']=stamp();data['process_pid']=os.getpid()
    temp=out/'live-status.tmp';temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.replace(temp,live)
    if journal.exists() and journal.stat().st_size>8*1024*1024:
        os.replace(journal,out/'run-journal-previous.jsonl')
    with journal.open('a',encoding='utf-8') as f:f.write(json.dumps(data,ensure_ascii=False)+'\n')
def main():
    if '--execute' not in sys.argv:print('Prepared only; no device access.');return
    if stop_file.exists():raise RuntimeError('Stop request present; do not arm until explicitly cleared')
    ports=[p for p in list_ports.comports() if p.vid==0x1A86]
    if len(ports)!=1:raise RuntimeError('Need one confirmed WCH serial port')
    data={'state':'STARTING','motion_commands':'NONE','random_commands_sent':0,'samples':0,'physical_observation':'PENDING_USER'}
    armed=False
    try:
        with serial.Serial(ports[0].device,115200,timeout=.08,write_timeout=.5) as link:
            link.reset_input_buffer()
            def exchange(command,prefix):
                link.write((command+'\n').encode('ascii'));deadline=time.monotonic()+1
                while time.monotonic()<deadline:
                    row=link.readline().decode('ascii',errors='replace').strip()
                    if row.startswith(prefix):return row
                    if row=='GIMBAL_NOT_RUNNING':raise RuntimeError('MCU stopped/rebooted; no automatic rearm')
                raise TimeoutError('No response to '+command)
            def snapshot():
                values=[int(v) for v in exchange('GIMBAL_STATUS','GIMBAL,').split(',')[1:]]
                keys=('ms','ready','active','mode','yaw_us','pitch_us','starts','stops','yaw_hz','pitch_hz')
                assert len(values)==len(keys);return dict(zip(keys,values))
            try:
                exchange('PING','PONG');before=snapshot();data['before']=before
                assert before['ready']==1 and before['active']==0 and before['yaw_us']==0 and before['pitch_us']==0
                assert before['yaw_hz']==1000000 and before['pitch_hz']==1000000
                armed=True;exchange('GIMBAL_RUN','GIMBAL_RUN_STARTED');data['random_commands_sent']=1
                data['started_at']=stamp();next_beat=time.monotonic();previous=before['ms']
                while not stop_file.exists():
                    exchange('GIMBAL_KEEPALIVE','GIMBAL_ALIVE')
                    s=snapshot()
                    assert s['ms']>=previous and s['starts']==before['starts']+1,'MCU reset; stop without rearm'
                    assert s['ready']==1 and s['active']==1 and s['mode']==4,'Continuous motion no longer active'
                    assert 1300<=s['yaw_us']<=1700 and 1350<=s['pitch_us']<=1650,'Pulse limit violation'
                    random_values=[int(v) for v in exchange('GIMBAL_RANDOM_STATUS','RANDOM,').split(',')[1:]]
                    assert len(random_values)==5
                    data.update(state='RUNNING',last=s,random=dict(zip(('target_yaw','target_pitch','targets','lease_age_ms','lease_stops'),random_values)))
                    data['samples']+=1;write_live(data);previous=s['ms']
                    if data['samples']==1:print(json.dumps({'state':'RUNNING','pid':os.getpid(),'first':s},ensure_ascii=False),flush=True)
                    next_beat+=.6
                    while time.monotonic()<next_beat and not stop_file.exists():time.sleep(.04)
                    if next_beat<time.monotonic()-.3:next_beat=time.monotonic()
                data.update(state='STOP_REQUESTED',stop_reason='USER_STOP_FILE')
            finally:
                if armed:
                    try:
                        exchange('GIMBAL_STOP','GIMBAL_STOPPED');after=snapshot()
                        assert after['active']==0 and after['yaw_us']==0 and after['pitch_us']==0
                        data.update(state='STOPPED',final=after)
                    except Exception as error:data.update(stop_reply_error=str(error),mcu_lease_stop='EXPECTED_WITHIN3S_NOT_PHYSICALLY_CONFIRMED')
    except Exception as error:
        data.update(state='ERROR',error=str(error));print(json.dumps({'state':'ERROR','error':str(error)}),flush=True)
    finally:
        write_live(data);print(json.dumps({'state':data['state'],'samples':data['samples']}),flush=True)
if __name__=='__main__':main()
