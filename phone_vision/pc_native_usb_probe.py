"""Only P7 native USBFS diagnostic; fixed allowlisted messages, no motion."""
from pathlib import Path
import sys,json,base64,time,datetime
sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
import serial
from serial.tools import list_ports
root=Path(__file__).resolve().parents[2]
folder=root/'output/phone_board_link'/('pc-native-'+time.strftime('%Y%m%d-%H%M%S'));folder.mkdir(parents=True)
ports=[p for p in list_ports.comports() if p.vid==0x1a86 and p.pid==0xfe0c]
events=[];passed=0;error=None
def record(kind,data):
    events.append({'seq':len(events)+1,'monotonic_ns':time.monotonic_ns(),'direction':kind,'length':len(data),'data_b64':base64.b64encode(data).decode('ascii')})
try:
    if len(ports)!=1:raise RuntimeError('Expected unique native USBFS 1A86:FE0C port; found '+str(len(ports)))
    queries=[(b'PING\n',b'PONG\n'),(b'NATIVE_ID\n',b'NATIVE_USBFS,1\n')]+[(x+b'\n',x+b'\n') for x in (b'ZX_NATIVE_A01',b'ZX_NATIVE_B02',b'ZX_NATIVE_C03')]
    with serial.Serial(ports[0].device,115200,timeout=.2,write_timeout=1) as conn:
        conn.reset_input_buffer()
        for tx,expected in queries:
            record('TX_ATTEMPT',tx);sent=conn.write(tx);record('TX_ACCEPTED',tx[:sent]);conn.flush()
            if sent!=len(tx):raise RuntimeError('Partial TX')
            data=bytearray();deadline=time.monotonic()+3
            while time.monotonic()<deadline and len(data)<len(expected):
                chunk=conn.read(len(expected)-len(data))
                if chunk:record('RX',chunk);data.extend(chunk)
            if bytes(data)!=expected:raise RuntimeError('Reply differs or times out')
            passed+=1
except Exception as exc:error=str(exc)
result={'at':datetime.datetime.now().astimezone().isoformat(),'mode':'PC_NATIVE_USBFS','port':ports[0].device if len(ports)==1 else None,'passed':passed==5 and error is None,'replies':passed,'expected':5,'error':error,'motion_commands_sent':False}
(folder/'bytes.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events),encoding='utf-8')
(folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'folder':str(folder),**result},ensure_ascii=False))
raise SystemExit(0 if result['passed'] else 1)
