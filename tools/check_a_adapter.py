"""Only query A-board ranging and flash ID/status. No flash writes or motor actions."""
from pathlib import Path
import sys,json,time,datetime
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
import serial

def main(port='COM5',label='before_knob_removal'):
    out=ROOT/'知行回路软件/build/a_adapter_checks';out.mkdir(exist_ok=True)
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    path=out/(now.strftime('%Y%m%d-%H%M%S')+'-'+label+'.json')
    rec={'date':now.isoformat(),'port':port,'scope':'A_ADAPTER_READ_ONLY',
         'storage_writes':'NONE','motor_commands':'NONE','samples':[],'transcript':[]}
    try:
        with serial.Serial(port,115200,timeout=.1,write_timeout=1) as link:
            def query(cmd,prefix):
                link.write((cmd+'\n').encode('ascii'));end=time.monotonic()+3
                while time.monotonic()<end:
                    row=link.readline().decode('ascii',errors='replace').strip()
                    if row:rec['transcript'].append({'command':cmd,'reply':row})
                    if row.startswith(prefix):return [int(x) for x in row.split(',')[1:]]
                raise TimeoutError('No response: '+cmd)
            for _ in range(12):
                s=query('STATUS','STATUS,');r=query('RECOVERY_STATUS','RECOVERY,')
                f=query('STORAGE_STATUS','STORAGE,');e=query('ENCODER_STATUS','ENCODER,')
                rec['samples'].append({'status':s,'recovery':r,'storage':f,'knob':e})
                time.sleep(.35)
        a,b=rec['samples'][0],rec['samples'][-1]
        running=b['status'][0]>a['status'][0] and b['status'][1]>a['status'][1]
        flash_ok=all(x['storage'][0]==0xEF4017 and x['storage'][5]==1 for x in rec['samples'])
        valid=[x['status'][4] for x in rec['samples'] if x['status'][2]==0 and x['status'][3]==0 and x['recovery'][0]==0 and x['recovery'][3]==0 and x['recovery'][4]==0 and x['recovery'][5]!=3]
        rec.update(result='PASS_READ_COMMUNICATION' if running and flash_ok and len(valid)>=10 else 'PARTIAL_OR_FAILED',
                   time_and_measurement_progress=running,storage_id_hex=hex(b['storage'][0]),
                   flash_id_matches=f'{sum(x["storage"][0]==0xEF4017 for x in rec["samples"])}/{len(rec["samples"])}',
                   valid_distance_samples=len(valid),distance_min_max_mm=[min(valid),max(valid)] if valid else None,
                   physical_accuracy='NOT_VERIFIED',flash_write_and_power_cycle='NOT_TESTED')
    except Exception as e:rec.update(result='FAILED_TO_READ',error=str(e))
    path.write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in rec.items() if k not in ('samples','transcript')},ensure_ascii=False))
    print('Evidence:',path)
    return rec
if __name__=='__main__':main(*(sys.argv[1:]))
