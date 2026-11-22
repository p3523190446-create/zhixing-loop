"""Forward live phone detections to CH32 over the verified WCH UART; no motor control."""
from pathlib import Path
import argparse
import datetime
import json
import queue
import subprocess
import sys
import threading
import time
from receive import command, validate, DEFAULT_ADB, OUTPUT

sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
import serial

def packet(payload):
    crc=0
    for byte in payload.encode('ascii'):
        crc^=byte
        for _ in range(8):crc=((crc<<1)^(7 if crc&128 else 0))&255
    return (payload+'*%02X\n'%crc).encode('ascii')

def request(link,data,expected,timeout=.6):
    link.write(data)
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        line=link.readline().decode('ascii',errors='replace').strip()
        if line==expected:return line
        if line=='ERR':raise RuntimeError('CH32 rejected the packet')
    raise TimeoutError('CH32 reply missing')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',required=True)
    parser.add_argument('--adb',type=Path,default=DEFAULT_ADB)
    parser.add_argument('--duration',type=float,default=20)
    opt=parser.parse_args()
    if not 1<=opt.duration<=3600:raise ValueError('Duration out of range')
    entries=[x.split() for x in command(opt.adb,'devices').splitlines()[1:] if x.strip()]
    if len(entries)!=1 or entries[0][1]!='device':raise RuntimeError('One authorized phone required')
    device=entries[0][0] # Routing only; never persist phone identifiers.
    pid=command(opt.adb,'-s',device,'shell','pidof','cn.zhixing.vision')
    if not pid:raise RuntimeError('Open Zhixing vision on the phone')
    messages=queue.Queue(maxsize=64)
    process=subprocess.Popen([str(opt.adb),'-s',device,'logcat','--pid='+pid.split()[0],
        '-v','raw','-T','1','ZXR_VISION:I','*:S'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
        text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
    def reader():
        for line in process.stdout:
            item=(time.monotonic(),line)
            try:messages.put_nowait(item)
            except queue.Full:
                try:messages.get_nowait()
                except queue.Empty:pass
                try:messages.put_nowait(item)
                except queue.Full:pass
    threading.Thread(target=reader,daemon=True).start()
    OUTPUT.mkdir(exist_ok=True,parents=True)
    evidence=OUTPUT/('phone-ch32-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.jsonl')
    record={'source':'live phone native detections -> PC USB ADB -> WCH UART -> CH32 ACK',
        'motor_control_connected':False,'standalone_phone_to_board':False,
        'left_center_right_physical_validation':'SKIPPED_BY_USER',
        'frames_acked':0,'invalid_phone_messages':0,'stale_pc_frames_dropped':0,
        'object_frames':0,'empty_frames':0,'evidence':str(evidence),'result':'NOT_RUN'}
    previous=None;last_phone_ms=None;start=time.monotonic();last_print=0
    try:
        with serial.Serial(opt.port,115200,timeout=.06,write_timeout=.5) as link, evidence.open('w',encoding='utf-8') as log:
            link.reset_input_buffer()
            request(link,b'HELLO\n','ZXR,V1',3)
            record['handshake']='PASS'
            print('UART handshake passed; forwarding only new real phone results.',flush=True)
            try:
                while time.monotonic()-start<opt.duration:
                    try:arrival,line=messages.get(timeout=.2)
                    except queue.Empty:
                        if process.poll() is not None:raise RuntimeError('Phone log stream stopped')
                        continue
                    if not line.lstrip().startswith('{'):continue
                    if time.monotonic()-arrival>.5:
                        record['stale_pc_frames_dropped']+=1;continue
                    try:frame=validate(json.loads(line))
                    except (ValueError,TypeError,KeyError):
                        record['invalid_phone_messages']+=1;continue
                    # -T 1 can include a historic last log. Skip the first frame;
                    # require a newly advancing sequence and monotonic timestamp.
                    if previous is None:
                        previous=frame['seq'];last_phone_ms=frame['phone_ms'];continue
                    if frame['seq']<=previous or frame['phone_ms']<=last_phone_ms:continue
                    if frame['seq']>0xFFFFFFFF:raise RuntimeError('Sequence exceeds MCU packet range')
                    previous=frame['seq'];last_phone_ms=frame['phone_ms']
                    primary=max(frame['objects'],key=lambda x:x['score'],default=None)
                    values=[previous]+([primary['cls']]+[round(primary[k]*1000) for k in ('score','cx','cy')]
                        if primary else [255,0,0,0])
                    body=','.join(str(x) for x in values)
                    sent=packet('V1,'+body)
                    before=time.monotonic()
                    ack=request(link,sent,'ACK,'+body)
                    uart_roundtrip=(time.monotonic()-before)*1000
                    row={'pc_received_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        'phone':frame,'selected_primary':primary,'uart_packet':sent.decode('ascii').strip(),
                        'ch32_ack':ack,'pc_uart_roundtrip_ms':uart_roundtrip}
                    log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush()
                    record['frames_acked']+=1
                    record['object_frames' if primary else 'empty_frames']+=1
                    if time.monotonic()-last_print>=1:
                        last_print=time.monotonic()
                        print(json.dumps({'phone_seq':previous,'primary':primary['name'] if primary else None,
                            'ch32_ack':ack},ensure_ascii=True),flush=True)
            finally:
                # End the bounded demonstration with no retained target.
                try:request(link,b'HELLO\n','ZXR,V1');record['target_cleared_on_exit']=True
                except Exception:record['target_cleared_on_exit']=False
        if record['frames_acked']==0:raise RuntimeError('No fresh actual phone frames acknowledged')
        record['result']='LIVE_PHONE_CH32_ACK_PASS'
    except Exception as e:
        record['result']='FAIL';record['error']=str(e);raise
    finally:
        process.terminate()
        try:process.wait(timeout=3)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        (OUTPUT/'bridge-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(record,ensure_ascii=True),flush=True)

if __name__=='__main__':main()
