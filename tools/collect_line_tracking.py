"""Read-only line sensor sampling through P9. Never sends motion/calibration commands."""
from pathlib import Path
import argparse
import datetime
import json
import sys
import time

sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
import serial

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',required=True)
    parser.add_argument('--seconds',type=float,default=12)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    if not 1<=args.seconds<=60:parser.error('seconds must be between 1 and 60')
    root=Path(__file__).resolve().parents[2]
    output=args.out or root/'output/onboard_dashboard/line-tracking-20261025/static-samples.json'
    result={'recorded_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
            'port':args.port,'scope':'Real read-only P9 queries; no movement or calibration commands','samples':[]}
    s=serial.Serial();s.port=args.port;s.baudrate=115200;s.timeout=.1;s.write_timeout=1;s.dtr=False;s.rts=False
    def query(command):
        prefix='DRIVE,' if command=='DRIVE_STATUS' else command+','
        s.write((command+'\n').encode('ascii'));s.flush();end=time.monotonic()+.6
        while time.monotonic()<end:
            row=s.readline().decode('ascii',errors='replace').strip()
            if row.startswith(prefix):return row
            if row.startswith('ERR'):return row
        return None
    try:
        s.open()
        with s:
            s.reset_input_buffer();result['identity']=query('LINE_ID')
            if result['identity']!='LINE_ID,YB_8LP_UART4_PC10_PC11_STATIC_V1':
                raise RuntimeError('Expected line acquisition firmware identity was not returned')
            start=time.monotonic()
            while time.monotonic()-start<args.seconds:
                row={'elapsed_s':round(time.monotonic()-start,3)}
                for name in ['LINE_STATUS','LINE_ANALOG','LINE_DIGITAL','DRIVE_STATUS']:
                    row[name]=query(name)
                result['samples'].append(row)
                time.sleep(.35)
    except Exception as e:
        result['error']=str(e)
    finally:
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'identity':result.get('identity'),'count':len(result['samples']),
                      'first':result['samples'][0] if result['samples'] else None,
                      'last':result['samples'][-1] if result['samples'] else None,
                      'error':result.get('error'),'output':str(output)},ensure_ascii=False,indent=2))
    if result.get('error'):raise SystemExit(1)

if __name__=='__main__':main()
