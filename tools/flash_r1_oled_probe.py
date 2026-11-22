"""Back up the working vision firmware, flash OLED probe, and read live ACK telemetry."""
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

OUT=PROJECT/'知行回路软件/build/r1_oled_probe'
WORK=TOOLS/'r1-oled-probe'
ELF=WORK/'r1_oled_probe.elf'
BASE=TOOLS/'r1-vision-bridge/r1_vision_bridge.elf'
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
    source=PROJECT/'知行回路软件/board/r1_oled_probe'
    assert hashlib.sha256((source/'main.c').read_bytes()).hexdigest()==build['source_sha256']
    assert hashlib.sha256((source/'vision_uart.c').read_bytes()).hexdigest()==build['uart_source_sha256']
    assert hashlib.sha256((source/'oled_probe.c').read_bytes()).hexdigest()==build['probe_source_sha256']
    assert hashlib.sha256(ELF.with_suffix('.bin').read_bytes()).hexdigest()==build['binary_sha256']
    assert ELF.read_bytes()==(OUT/ELF.name).read_bytes()
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup=WORK/('before-oled-'+stamp+'.bin')
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
    with (OUT/'openocd-oled.log').open('w',encoding='utf-8') as log:
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
            assert len(original)==262144 and original[:len(baseline)]==baseline, 'Current firmware differs from known vision baseline; stop before flash'
            saved=OUT/backup.name;saved.write_bytes(original)
            record['backup']={'path':str(saved),'sha256':hashlib.sha256(original).hexdigest(),
                              'bytes':len(original),'matches_vision_baseline':True}
            print('Current vision firmware backed up and matched.',flush=True)
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
                first=status()
                def oled_status():
                    link.write(b'OLED_STATUS\n');end=time.monotonic()+3
                    while time.monotonic()<end:
                        row=link.readline().decode('ascii',errors='replace').strip()
                        if row.startswith('OLED,'):
                            values=[int(x) for x in row.split(',')[1:]]
                            assert len(values)==5
                            return dict(zip(['scans','ack_3c','ack_3d','bus_error','idle_lines'],values))
                    raise TimeoutError('OLED diagnostic reply missing')
                initial=oled_status()
                time.sleep(2.2)
                latest=oled_status();last=status()
                record['oled_samples']=[initial,latest]
                record['range_samples']=[first,last]
                assert latest['scans']>initial['scans'] and last['tick_ms']>first['tick_ms']
                assert last['range_rounds']>first['range_rounds'] and last['range_init_error']==0
                record['oled_bus']='ACK_PASS' if not latest['bus_error'] and (latest['ack_3c'] or latest['ack_3d']) else 'NOT_DETECTED'
                record['oled_7bit_addresses']=[a for a,k in [('0x3C','ack_3c'),('0x3D','ack_3d')] if latest[k]]
                record['display_render']='NOT_IMPLEMENTED'
                record['transcript']=transcript
            record['uart']='PASS'
            record['checks']=['HELLO/PING','OLED online ACK diagnostics','distance sampling and timer continue']
            print(json.dumps({'flash':record['flash'],'readback':record['readback'],'uart':record['uart'],
                'oled_bus':record['oled_bus'],'oled_samples':record['oled_samples']},ensure_ascii=True),flush=True)
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
            (OUT/'flash-oled-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            (OUT/'gdb-oled.log').write_text(''.join(lines),encoding='utf-8')

if __name__=='__main__':main()
