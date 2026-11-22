"""Receive-only UART capture for isolated USBHS host enumeration."""
from pathlib import Path
import sys,time,json,base64,hashlib,datetime,socket,subprocess
sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
import serial
from serial.tools import list_ports
root=Path(__file__).resolve().parents[2]
folder=root/'output/usbhs_camera_probe'/time.strftime('%Y%m%d-%H%M%S');folder.mkdir(parents=True)
ports=[p for p in list_ports.comports() if p.vid==0x1a86 and p.pid==0x8010]
assert len(ports)==1,'Expected one P9 UART'
events=[];pending=bytearray();lines=[];error=None;complete=False;seen_at=None
with serial.Serial(ports[0].device,115200,timeout=.2) as conn:
    if '--reset-existing-probe' in sys.argv:
        stem='r1_usbhs_camera_frame' if '--frame' in sys.argv else 'r1_usbhs_camera_probe'
        proof=json.loads((root/'知行回路软件/build'/stem/'flash-verification.json').read_text(encoding='utf8'))
        assert proof['flash']=='PASS' and proof['readback']=='PASS'
        ocd=Path.home()/'Documents/ch32-tools/MRS2/resources/app/resources/win32/components/WCH/OpenOCD/OpenOCD/bin'
        try:
            socket.create_connection(('127.0.0.1',6666),timeout=.2).close()
            raise RuntimeError('Unrelated debug server running')
        except OSError:pass
        with (folder/'reset-openocd.log').open('w',encoding='utf8') as log:
            process=subprocess.Popen([str(ocd/'openocd.exe'),'-f','wch-riscv.cfg'],cwd=ocd,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            link=None
            try:
                for attempt in range(40):
                    if process.poll() is not None:raise RuntimeError('Debug server exited')
                    try:link=socket.create_connection(('127.0.0.1',6666),timeout=.2);break
                    except OSError:time.sleep(.2)
                assert link is not None
                def command(text):
                    link.settimeout(4);link.sendall(text.encode()+b'\x1a');reply=b''
                    while not reply.endswith(b'\x1a'):
                        block=link.recv(4096)
                        if not block:raise RuntimeError('Debug reset disconnected')
                        reply+=block
                    assert not reply.startswith(b'error'),reply
                command('reset halt');command('resume 0');command('shutdown')
            finally:
                if link:link.close()
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=3)
    end=time.monotonic()+120
    while time.monotonic()<end:
        chunk=conn.read(512)
        if chunk:
            events.append({'seq':len(events)+1,'monotonic_ns':time.monotonic_ns(),'wall_ns':time.time_ns(),'direction':'RX','length':len(chunk),'data_b64':base64.b64encode(chunk).decode()})
            pending.extend(chunk)
            while b'\n' in pending:
                line,_,tail=pending.partition(b'\n');pending=bytearray(tail);text=line.rstrip(b'\r').decode('ascii',errors='replace');lines.append(text)
                if text.startswith(('USBHS_STAGE','USBHS_ID','USBHS_RESULT','UVC_STAGE','UVC_FRAME','UVC_RESULT')):print(text,flush=True)
                if '--frame' in sys.argv:
                    if text.startswith('UVC_RESULT,'):seen_at=time.monotonic()
                    if text=='UVC_RESULT,FRAME_READ':complete=True
                else:
                    if text.startswith('USBHS_RESULT,') or text.startswith('USBHS_ID,'):seen_at=time.monotonic()
                    if text=='USBHS_RESULT,DESCRIPTORS_READ_NO_VIDEO':complete=True
        if complete:break
        if seen_at and time.monotonic()-seen_at>3:break
# Preserve original bytes before any descriptor parsing assertions.
(folder/'uart.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events),encoding='utf8')
(folder/'lines.json').write_text(json.dumps(lines,indent=2),encoding='utf8')
blobs={}
for line in lines:
    if not line.startswith('USBHS_BYTES,'):continue
    _,kind,offset,payload=line.split(',',3);buf=blobs.setdefault(kind,bytearray());assert int(offset)==len(buf),'Noncontiguous descriptor capture';buf.extend(bytes.fromhex(payload))
interfaces=[];endpoints=[];mjpeg_frames=[]
device=bytes(blobs.get('DEVICE',b''));config=bytes(blobs.get('CONFIG',b''))
if complete:
    assert len(device)==18 and device[8:12]==bytes.fromhex('5F14EC02')
    assert len(config)>=9 and len(config)==int.from_bytes(config[2:4],'little')
    pos=0;interface=None
    while pos<len(config):
        n=config[pos];assert n>=2 and pos+n<=len(config),'Malformed descriptor'
        d=config[pos:pos+n];kind=d[1]
        if kind==4:
            assert n>=9;interface={'id':d[2],'alternate':d[3],'class':d[5],'subclass':d[6]};interfaces.append(interface)
        elif kind==5:
            assert n>=7;endpoints.append({'interface':interface,'address':d[2],'transfer_type':d[3]&3,'max_packet_field':int.from_bytes(d[4:6],'little'),'interval':d[6]})
        elif kind==0x24 and interface and interface['class']==14 and interface['subclass']==2 and n>=26 and d[2]==7:
            mjpeg_frames.append({'interface':interface,'index':d[3],'width':int.from_bytes(d[5:7],'little'),'height':int.from_bytes(d[7:9],'little'),'max_frame_bytes':int.from_bytes(d[17:21],'little'),'default_interval_100ns':int.from_bytes(d[21:25],'little'),'interval_type':d[25]})
        pos+=n
if complete and '--frame' in sys.argv:
    jpeg=bytes(blobs.get('JPEG',b''));assert jpeg.startswith(b'\xff\xd8') and jpeg.endswith(b'\xff\xd9');(folder/'frame.jpg').write_bytes(jpeg)
report={'result':('ONE_JPEG_FRAME_READ_PASS' if '--frame' in sys.argv else 'DESCRIPTORS_READ_PASS') if complete else 'NO_COMPLETE_DESCRIPTOR_CAPTURE','scope':'USBHS target enumeration / single frame experiment; no phone forwarding','interfaces':interfaces,'endpoints':endpoints,'mjpeg_frames':mjpeg_frames,'lines':lines,'uart_transmissions':0,'error':error,'captured_bytes':sum(e['length'] for e in events)}
for name,buf in blobs.items():(folder/(name.lower()+'-descriptor.bin')).write_bytes(buf)
(folder/'uart.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events),encoding='utf8')
(folder/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'folder':str(folder),'result':report['result'],'interfaces':interfaces,'endpoints':endpoints,'mjpeg_frames':mjpeg_frames},ensure_ascii=False),flush=True)
