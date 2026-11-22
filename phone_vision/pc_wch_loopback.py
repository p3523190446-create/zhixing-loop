"""Requires J2 WCH TX_0/RX_0 short, CH32 UART isolated. No motion commands."""
from pathlib import Path
import argparse, base64, datetime, json, time, sys
sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
import serial
from serial.tools import list_ports

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--j2-loopback-ready',action='store_true',required=True)
    parser.parse_args()
    ports=[p for p in list_ports.comports() if p.vid==0x1a86 and p.pid==0x8010]
    root=Path(__file__).resolve().parents[2]
    folder=root/'output/phone_board_link'/('pc-loopback-'+time.strftime('%Y%m%d-%H%M%S'))
    folder.mkdir(parents=True)
    events=[];passed=0;error=None
    def record(direction,data):
        events.append({'seq':len(events)+1,'monotonic_ns':time.monotonic_ns(),'direction':direction,
            'length':len(data),'data_b64':base64.b64encode(data).decode('ascii')})
    try:
        if len(ports)!=1:raise RuntimeError('Expected exactly one 1A86:8010 WCH CDC port; found '+str(len(ports)))
        with serial.Serial(ports[0].device,115200,timeout=.2,write_timeout=1) as conn:
            conn.reset_input_buffer()
            for token in (b'ZX_PC_A01\n',b'ZX_PC_B02\n',b'ZX_PC_C03\n'):
                record('TX_ATTEMPT',token)
                sent=conn.write(token);record('TX_ACCEPTED',token[:sent]);conn.flush()
                if sent!=len(token):raise RuntimeError('Partial PC UART write')
                data=bytearray();deadline=time.monotonic()+3
                while time.monotonic()<deadline and len(data)<len(token):
                    chunk=conn.read(len(token)-len(data))
                    if chunk:record('RX',chunk);data.extend(chunk)
                if bytes(data)!=token:raise RuntimeError('PC echo mismatch or timeout; see retained bytes')
                passed+=1
    except Exception as exc:error=str(exc)
    finally:
        (folder/'bytes.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events),encoding='utf-8')
        result={'at':datetime.datetime.now().astimezone().isoformat(),'mode':'PC_WCH_LOOPBACK',
            'port':ports[0].device if len(ports)==1 else None,'wch_ports_detected':len(ports),'passed':passed==3 and error is None,'replies':passed,'expected':3,'error':error,
            'mcu_communication':'NOT_TESTED','motion_commands_sent':False}
        (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'folder':str(folder),**result},ensure_ascii=False))
    return 0 if passed==3 and error is None else 1

if __name__=='__main__':raise SystemExit(main())
