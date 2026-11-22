"""Back up the current warning firmware, flash, read back, and test UART on R1."""
from pathlib import Path
import datetime
import hashlib
import json
import queue
import socket
import subprocess
import sys
import threading
import time

PROJECT=Path(__file__).resolve().parents[2]
TOOLS=Path.home()/'Documents/ch32-tools'
sys.path.insert(0,str(TOOLS/'python-support'))
import serial

OUT=PROJECT/'知行回路软件/build/r1_vision_bridge'
WORK=TOOLS/'r1-vision-bridge'
ELF=WORK/'r1_vision_bridge.elf'
BASE=TOOLS/'r1-distance-guard/r1_distance_guard.elf'
OCDBIN=TOOLS/'MRS2/resources/app/resources/win32/components/WCH/OpenOCD/OpenOCD/bin'

def crc8(s):
    crc=0
    for b in s.encode('ascii'):
        crc^=b
        for _ in range(8):crc=((crc<<1)^ (7 if crc&128 else 0))&255
    return crc

def packet(payload):return (payload+'*%02X\n'%crc8(payload)).encode('ascii')

def main():
    port=sys.argv[1] if len(sys.argv)==2 else None
    if not port:raise RuntimeError('Specify the verified WCH serial port, e.g. COM5')
    build=json.loads((OUT/'build_result.json').read_text(encoding='utf-8'))
    source=PROJECT/'知行回路软件/board/r1_vision_bridge'
    assert hashlib.sha256((source/'main.c').read_bytes()).hexdigest()==build['source_sha256']
    assert hashlib.sha256((source/'vision_uart.c').read_bytes()).hexdigest()==build['uart_source_sha256']
    assert hashlib.sha256(ELF.with_suffix('.bin').read_bytes()).hexdigest()==build['binary_sha256']
    assert ELF.read_bytes()==(OUT/ELF.name).read_bytes()
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup=WORK/('before-vision-'+stamp+'.bin')
    record={'date':datetime.date.today().isoformat(),'firmware_sha256':build['binary_sha256'],
            'flash':'NOT_RUN','readback':'NOT_RUN','uart':'NOT_RUN','motor_control':'NOT_IMPLEMENTED'}
    q=queue.Queue();lines=[];token=0;ocd=gdb=None;flashed=False
    def command(text,timeout=20):
        nonlocal token
        token+=1;prefix=str(token)
        gdb.stdin.write(prefix+text+'\n');gdb.stdin.flush()
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            try:row=q.get(timeout=.2)
            except queue.Empty:continue
            lines.append(row)
            if row.startswith(prefix+'^'):
                if '^error' in row:raise RuntimeError(row.strip())
                return row
        raise TimeoutError(text)
    def console(text,timeout=20):return command('-interpreter-exec console '+json.dumps(text),timeout)
    with (OUT/'openocd-vision.log').open('w',encoding='utf-8') as log:
        try:
            ocd=subprocess.Popen([str(OCDBIN/'openocd.exe'),'-f','wch-riscv.cfg'],cwd=OCDBIN,
                stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            for _ in range(60):
                if ocd.poll() is not None:raise RuntimeError('OpenOCD exited')
                try:
                    with socket.create_connection(('127.0.0.1',3333),timeout=.2):pass
                    break
                except OSError:time.sleep(.2)
            else:raise TimeoutError('OpenOCD')
            gdb=subprocess.Popen([str(TOOLS/'gcc/bin/riscv-none-embed-gdb.exe'),'--interpreter=mi2',str(ELF)],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
                creationflags=subprocess.CREATE_NO_WINDOW)
            def reader():
                for row in gdb.stdout:q.put(row)
            threading.Thread(target=reader,daemon=True).start()
            command('-gdb-set mi-async on')
            command('-target-select extended-remote localhost:3333')
            console('dump binary memory '+backup.as_posix()+' 0x00000000 0x00040000',45)
            original=backup.read_bytes();baseline=BASE.with_suffix('.bin').read_bytes()
            assert len(original)==262144 and original[:len(baseline)]==baseline, 'Current firmware differs from known warning baseline; stop before flash'
            saved=OUT/backup.name;saved.write_bytes(original)
            record['backup']={'path':str(saved),'sha256':hashlib.sha256(original).hexdigest(),
                              'bytes':len(original),'matches_warning_baseline':True}
            print('Current warning firmware backed up and matched.',flush=True)
            flashed=True
            command('-target-download',45);record['flash']='PASS'
            start=len(lines);console('compare-sections',30)
            compare=''.join(lines[start:]);record['compare_sections']=compare
            assert compare.count('matched')>=4 and 'MIS-MATCH' not in compare
            record['readback']='PASS'
            console('monitor reset halt')
            command('-exec-continue');time.sleep(4)
            with serial.Serial(port,115200,timeout=.15,write_timeout=1) as link:
                link.reset_input_buffer()
                transcript=[]
                def exchange(data,expected):
                    link.write(data);end=time.monotonic()+3
                    while time.monotonic()<end:
                        reply=link.readline().decode('ascii',errors='replace').strip()
                        if not reply:continue
                        transcript.append({'sent':data.decode('ascii').strip(),'received':reply})
                        if reply==expected:return
                    raise RuntimeError('UART timeout; expected '+expected)
                def status():
                    link.write(b'STATUS\n');end=time.monotonic()+3
                    while time.monotonic()<end:
                        reply=link.readline().decode('ascii',errors='replace').strip()
                        if not reply.startswith('STATUS,'):continue
                        values=[int(x) for x in reply.split(',')[1:]]
                        names=['tick_ms','range_rounds','range_init_error','range_status',
                            'range_corrected_mm','vision_valid','vision_class','vision_seq',
                            'vision_accepted','vision_rejected','vision_rx_errors']
                        assert len(values)==len(names)
                        return dict(zip(names,values))
                    raise TimeoutError('Live UART telemetry missing')
                exchange(b'HELLO\n','ZXR,V1')
                exchange(b'PING\n','PONG')
                exchange(packet('V1,1,39,500,500,500'),'ACK,1,39,500,500,500')
                live=status();record['during_synthetic_communication_test']=live
                assert live['vision_valid']==1 and live['vision_class']==39 and live['vision_accepted']==1
                exchange(b'V1,2,39,500,500,500*XX\n','ERR')
                exchange(packet('V1,1,39,500,500,500'),'ERR')
                exchange(packet('V1,2,80,500,500,500'),'ERR')
                # An overlong line is discarded without generating a target.
                link.write(b'X'*110+b'\n');time.sleep(.1)
                exchange(b'PING\n','PONG')
                time.sleep(1.2)
                stale=status();record['after_sender_stopped']=stale
                assert stale['vision_valid']==0 and stale['vision_class']==255
                assert stale['vision_rejected']>=4 and stale['vision_rx_errors']==0
                assert stale['tick_ms']>live['tick_ms'] and stale['range_rounds']>live['range_rounds']
                assert stale['range_init_error']==0
                exchange(packet('V1,3,255,0,0,0'),'ACK,3,255,0,0,0')
                exchange(b'HELLO\n','ZXR,V1') # End with no synthetic target.
                record['transcript']=transcript
            record['uart']='PASS'
            record['checks']=['HELLO/PING','echoed synthetic packet (not actual detection evidence)',
                'bad checksum rejected','duplicate sequence rejected','unknown class rejected',
                'overlong line discarded with recovery','target invalidated after 1s',
                'distance sampling and timer continue','explicit empty target accepted']
            print('FLASH_READBACK_UART_PASS',flush=True)
        except Exception as e:
            record['error']=str(e)
            if flashed and gdb is not None:
                try:
                    try:command('-exec-interrupt');time.sleep(.2)
                    except Exception:pass
                    command('-file-exec-and-symbols '+json.dumps(str(BASE)))
                    command('-target-download',45);console('monitor reset halt')
                    command('-exec-continue');record['rollback']='BASELINE_RESTORED'
                except Exception as restore:record['rollback_error']=str(restore)
            raise
        finally:
            if gdb is not None and gdb.poll() is None:
                try:command('-exec-continue',3)
                except Exception:pass
                try:command('-target-detach',3)
                except Exception:pass
                try:command('-gdb-exit',3)
                except Exception:gdb.terminate()
            if ocd is not None and ocd.poll() is None:
                ocd.terminate()
                try:ocd.wait(timeout=3)
                except subprocess.TimeoutExpired:ocd.kill();ocd.wait()
            (OUT/'flash-uart-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            (OUT/'gdb-vision.log').write_text(''.join(lines),encoding='utf-8')

if __name__=='__main__':main()
