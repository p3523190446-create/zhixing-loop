"""Back up known screen-layout firmware, install motor UART diagnostic and verify.

Only run with the physical four wheels suspended and confirmed WCH-Link port.
The diagnostic sends zero PWM and voltage queries; no nonzero motion.
"""
from pathlib import Path
import datetime,hashlib,json,queue,socket,subprocess,sys,threading,time

PROJECT=Path(__file__).resolve().parents[2]
TOOLS=Path.home()/'Documents/ch32-tools'
sys.path.insert(0,str(TOOLS/'python-support'))
import serial
OUT=PROJECT/'知行回路软件/build/r1_motor_probe'
WORK=TOOLS/'r1-motor-probe'
ELF=WORK/'r1_motor_probe.elf'
BASE=TOOLS/'r1-screen-layout/r1_screen_layout.elf'
OCDBIN=TOOLS/'MRS2/resources/app/resources/win32/components/WCH/OpenOCD/OpenOCD/bin'

class DebugLink:
    def __init__(self,log):
        self.q=queue.Queue();self.lines=[];self.token=0;self.gdb=None
        self.ocd=subprocess.Popen([str(OCDBIN/'openocd.exe'),'-f','wch-riscv.cfg'],cwd=OCDBIN,
            stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        for _ in range(60):
            if self.ocd.poll() is not None:raise RuntimeError('OpenOCD exited; inspect log')
            try:
                with socket.create_connection(('127.0.0.1',3333),timeout=.2):pass
                break
            except OSError:time.sleep(.2)
        else:raise TimeoutError('WCH-Link debug server unavailable')
        self.gdb=subprocess.Popen([str(TOOLS/'gcc/bin/riscv-none-embed-gdb.exe'),'--interpreter=mi2',str(ELF)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
            creationflags=subprocess.CREATE_NO_WINDOW)
        def reader():
            for row in self.gdb.stdout:self.q.put(row)
        threading.Thread(target=reader,daemon=True).start()
        self.command('-gdb-set mi-async on')
        self.command('-target-select extended-remote localhost:3333')
    def command(self,text,timeout=20):
        self.token+=1;prefix=str(self.token)
        self.gdb.stdin.write(prefix+text+'\n');self.gdb.stdin.flush()
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            try:row=self.q.get(timeout=.2)
            except queue.Empty:continue
            self.lines.append(row)
            if row.startswith(prefix+'^'):
                if '^error' in row:raise RuntimeError(row.strip())
                return row
        raise TimeoutError(text)
    def console(self,text,timeout=20):
        return self.command('-interpreter-exec console '+json.dumps(text),timeout)
    def run_reset(self):
        self.console('monitor reset halt');self.console('set $pc = 0');self.command('-exec-continue')
    def close(self):
        if self.gdb is not None and self.gdb.poll() is None:
            for cmd in ('-exec-continue','-target-detach','-gdb-exit'):
                try:self.command(cmd,3)
                except Exception:pass
            if self.gdb.poll() is None:self.gdb.terminate()
        if self.ocd.poll() is None:
            self.ocd.terminate()
            try:self.ocd.wait(timeout=3)
            except subprocess.TimeoutExpired:self.ocd.kill();self.ocd.wait()

def main():
    if len(sys.argv)!=2:raise RuntimeError('Specify the currently verified WCH-Link COM port')
    port=sys.argv[1]
    # Check exclusive access before any debug/flash mutation.
    with serial.Serial(port,115200,timeout=.1):pass
    build=json.loads((OUT/'build_result.json').read_text(encoding='utf-8'))
    for name,digest in build['all_source_sha256'].items():
        assert hashlib.sha256((PROJECT/'知行回路软件/board'/ELF.stem/name).read_bytes()).hexdigest()==digest,name
    assert ELF.read_bytes()==(OUT/ELF.name).read_bytes()
    assert hashlib.sha256(ELF.with_suffix('.bin').read_bytes()).hexdigest()==build['binary_sha256']
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup=WORK/('before-motor-probe-'+stamp+'.bin')
    record={'date':datetime.datetime.now().isoformat(),'port':port,'firmware_sha256':build['binary_sha256'],
        'flash':'NOT_RUN','readback':'NOT_RUN','driver_uart':'NOT_RUN','nonzero_motor_commands':'NONE'}
    debug=None;flashed=False
    with (OUT/'openocd-motor.log').open('w',encoding='utf-8') as log:
        try:
            debug=DebugLink(log)
            debug.console('dump binary memory '+backup.as_posix()+' 0x00000000 0x00040000',45)
            original=backup.read_bytes();baseline=BASE.with_suffix('.bin').read_bytes()
            saved=OUT/backup.name;saved.write_bytes(original)
            matches=len(original)==262144 and original[:len(baseline)]==baseline
            record['backup']={'path':str(saved),'sha256':hashlib.sha256(original).hexdigest(),'bytes':len(original),'baseline':BASE.stem,'matches_baseline':matches}
            assert matches,'Live firmware differs from verified '+BASE.stem+' baseline; no flash performed'
            print('Known baseline backed up.',flush=True)
            flashed=True;debug.command('-target-download',45);record['flash']='PASS'
            at=len(debug.lines);debug.console('compare-sections',30)
            comparison=''.join(debug.lines[at:]);record['compare_sections']=comparison
            assert comparison.count('matched')>=4 and 'MIS-MATCH' not in comparison
            record['readback']='PASS';debug.run_reset();time.sleep(3)
            with serial.Serial(port,115200,timeout=.1,write_timeout=1) as link:
                transcript=[]
                def exchange(command,prefix):
                    link.write(command.encode('ascii')+b'\n');end=time.monotonic()+3
                    while time.monotonic()<end:
                        row=link.readline().decode('ascii',errors='replace').strip()
                        if row:transcript.append({'command':command,'reply':row})
                        if row.startswith(prefix):return row
                    raise TimeoutError('No reply to '+command)
                assert exchange('PING','PONG')=='PONG'
                def snapshot():
                    rows={c:exchange(c,p) for c,p in [('STATUS','STATUS,'),('RECOVERY_STATUS','RECOVERY,'),
                        ('SETTINGS_STATUS','SETTINGS,'),('OLED_SCREEN','SCREEN,'),('OLED2_SCREEN','SCREEN2,'),
                        ('OLED3_SCREEN','SCREEN3,'),('MOTOR_STATUS','MOTOR,'),('MOTOR_RAW','MOTORRAW,')]}
                    rows['driver_raw_ascii']=bytes.fromhex(rows['MOTOR_RAW'].split(',',1)[1]).decode('ascii',errors='replace')
                    return rows
                first=snapshot();time.sleep(3);last=snapshot()
                record['samples']=[first,last]
                a=[int(x) for x in first['STATUS'].split(',')[1:]]
                b=[int(x) for x in last['STATUS'].split(',')[1:]]
                assert b[0]>a[0] and b[1]>a[1],'Timer/range sampling stopped'
                record['timer_and_range_sampling']='PASS'
                for c in ('OLED_SCREEN','OLED2_SCREEN','OLED3_SCREEN'):
                    aa=[int(x) for x in first[c].split(',')[1:]]
                    bb=[int(x) for x in last[c].split(',')[1:]]
                    assert bb[0]>aa[0] and bb[1]==1 and bb[2]==0,c+' failed'
                record['three_oled_transfers']='PASS'
                vals=[int(x) for x in last['MOTOR_STATUS'].split(',')[1:]]
                record['driver_uart']='RX_OBSERVED_NO_ERRORS' if vals[0]>0 and vals[1]==0 and vals[2]==0 else 'NOT_VERIFIED'
                record['transcript']=transcript
                print(json.dumps({'flash':record['flash'],'readback':record['readback'],
                    'driver_uart':record['driver_uart'],'raw':last['driver_raw_ascii'],
                    'samples':record['samples']},ensure_ascii=False),flush=True)
        except Exception as e:
            record['error']=str(e)
            if flashed and debug is not None:
                try:
                    try:debug.command('-exec-interrupt');time.sleep(.2)
                    except Exception:pass
                    debug.command('-file-exec-and-symbols '+json.dumps(str(BASE)))
                    debug.command('-target-download',45);debug.run_reset();record['rollback']='SCREEN_LAYOUT_RESTORED'
                except Exception as restore:record['rollback_error']=str(restore)
            raise
        finally:
            if debug is not None:
                debug.close();(OUT/'gdb-motor.log').write_text(''.join(debug.lines),encoding='utf-8')
            (OUT/'flash-motor-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
