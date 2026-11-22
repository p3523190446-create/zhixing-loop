"""Back up known single OLED firmware, install dual OLED and sensor recovery."""
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

OUT=PROJECT/'知行回路软件/build/r1_oled_triple'
WORK=TOOLS/'r1-oled-triple'
ELF=WORK/'r1_oled_triple.elf'
BASE=TOOLS/'r1-vision-ui/r1_vision_ui.elf'
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
    source=PROJECT/'知行回路软件/board/r1_oled_triple'
    for name,digest in build['all_source_sha256'].items():
        assert hashlib.sha256((source/name).read_bytes()).hexdigest()==digest,name
    assert hashlib.sha256(ELF.with_suffix('.bin').read_bytes()).hexdigest()==build['binary_sha256']
    assert ELF.read_bytes()==(OUT/ELF.name).read_bytes()
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup=WORK/('before-display-'+stamp+'.bin')
    record={'date':'2026-10-07','firmware_sha256':build['binary_sha256'],
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
    with (OUT/'openocd-display.log').open('w',encoding='utf-8') as log:
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
            assert len(original)==262144 and original[:len(baseline)]==baseline, 'Current firmware differs from known vision UI baseline; stop before flash'
            saved=OUT/backup.name;saved.write_bytes(original)
            record['backup']={'path':str(saved),'sha256':hashlib.sha256(original).hexdigest(),
                              'bytes':len(original),'matches_vision_ui_baseline':True}
            print('Current dual-screen firmware backed up and matched.',flush=True)
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
                def screen_status():
                    link.write(b'OLED_SCREEN\n');end=time.monotonic()+3
                    while time.monotonic()<end:
                        row=link.readline().decode('ascii',errors='replace').strip()
                        if row.startswith('SCREEN,'):
                            values=[int(x) for x in row.split(',')[1:]]
                            assert len(values)==3
                            return dict(zip(['frames','ready','errors'],values))
                    raise TimeoutError('Screen diagnostic reply missing')
                def diagnostic(command,prefix,names):
                    link.write(command.encode('ascii')+b'\n');end=time.monotonic()+3
                    while time.monotonic()<end:
                        row=link.readline().decode('ascii',errors='replace').strip()
                        if row.startswith(prefix+','):
                            values=[int(x) for x in row.split(',')[1:]]
                            assert len(values)==len(names)
                            return dict(zip(names,values))
                    raise TimeoutError(command+' missing')
                def oled2_status():return diagnostic('OLED2_STATUS','OLED2',['scans','ack_3c','ack_3d','bus_error','idle_lines'])
                def screen2_status():return diagnostic('OLED2_SCREEN','SCREEN2',['frames','ready','errors'])
                def recovery():return diagnostic('RECOVERY_STATUS','RECOVERY',['needs_reinit','attempts','successes','init_error','last_error','guard_state','red','green','offset_um'])
                third_bus_first=diagnostic('OLED3_STATUS','OLED3',['scans','ack_3c','ack_3d','bus_error','idle_lines'])
                third_screen_first=diagnostic('OLED3_SCREEN','SCREEN3',['frames','ready','errors'])
                second_bus_first=oled2_status();second_screen_first=screen2_status();recovery_first=recovery()
                screen_first=screen_status()
                initial=oled_status()
                time.sleep(2.2)
                latest=oled_status();last=status()
                record['oled_samples']=[initial,latest]
                record['range_samples']=[first,last]
                assert latest['scans']>initial['scans'] and last['tick_ms']>first['tick_ms']
                assert last['range_rounds']>first['range_rounds'] and last['range_init_error']==0
                record['oled_bus']='ACK_PASS' if not latest['bus_error'] and (latest['ack_3c'] or latest['ack_3d']) else 'NOT_DETECTED'
                record['oled_7bit_addresses']=[a for a,k in [('0x3C','ack_3c'),('0x3D','ack_3d')] if latest[k]]
                screen_last=screen_status()
                record['screen_samples']=[screen_first,screen_last]
                assert screen_last['frames']>screen_first['frames'] and screen_last['ready']==1 and screen_last['errors']==0
                second_bus_last=oled2_status();second_screen_last=screen2_status();recovery_last=recovery()
                record['second_bus_samples']=[second_bus_first,second_bus_last]
                record['second_screen_samples']=[second_screen_first,second_screen_last]
                record['recovery_samples']=[recovery_first,recovery_last]
                second_ok=second_bus_last['ack_3c'] or second_bus_last['ack_3d']
                record['second_oled_bus']='ACK_PASS' if second_ok and not second_bus_last['bus_error'] else 'NOT_DETECTED'
                record['second_display_transfer']='PASS' if second_screen_last['ready'] and second_screen_last['frames']>second_screen_first['frames'] else 'NOT_READY'
                assert recovery_last['needs_reinit']==0 and recovery_last['init_error']==0 and recovery_last['offset_um']==13000
                third_bus_last=diagnostic('OLED3_STATUS','OLED3',['scans','ack_3c','ack_3d','bus_error','idle_lines'])
                third_screen_last=diagnostic('OLED3_SCREEN','SCREEN3',['frames','ready','errors'])
                record['third_bus_samples']=[third_bus_first,third_bus_last]
                record['third_screen_samples']=[third_screen_first,third_screen_last]
                third_ok=(third_bus_last['ack_3c'] or third_bus_last['ack_3d']) and not third_bus_last['bus_error']
                record['third_oled_bus']='ACK_PASS' if third_ok else 'NOT_DETECTED'
                record['third_display_transfer']='PASS' if third_screen_last['ready'] and third_screen_last['frames']>third_screen_first['frames'] and third_screen_last['errors']==0 else 'NOT_READY'
                assert second_screen_last['ready']==1 and second_screen_last['frames']>second_screen_first['frames'] and second_screen_last['errors']==0
                if third_ok:assert record['third_display_transfer']=='PASS'
                record['physical_reconnect']='NOT_RETESTED_UI_ONLY_CHANGE' 
                record['display_transfer']='PASS'
                record['physical_screen']='PENDING_USER_OBSERVATION'
                record['controller_identification']='UNCONFIRMED; SSD1306 128x64 compatibility trial'
                record['display_render']='PENDING_USER_OBSERVATION' 
                record['transcript']=transcript
            record['uart']='PASS'
            record['checks']=['HELLO/PING','OLED online ACK diagnostics','distance sampling and timer continue']
            print(json.dumps({'flash':record['flash'],'readback':record['readback'],'uart':record['uart'],
                'oled_bus':record['oled_bus'],'oled_samples':record['oled_samples'],'screen_samples':record['screen_samples'],'second_oled_bus':record['second_oled_bus'],'second_screen_samples':record['second_screen_samples'],'recovery_samples':record['recovery_samples'],'third_oled_bus':record['third_oled_bus'],'third_screen_samples':record['third_screen_samples']},ensure_ascii=True),flush=True)
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
            (OUT/'flash-display-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            (OUT/'gdb-display.log').write_text(''.join(lines),encoding='utf-8')

if __name__=='__main__':main()
