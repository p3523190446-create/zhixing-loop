"""Install only after user confirms driver battery disconnected and CH32 USB ready.
Native OpenOCD RPC, 256KiB backup, verified baseline, bytewise readback, rollback.
No GDB, no motor nonzero or settings commands.
"""
from pathlib import Path
import datetime,hashlib,json,socket,subprocess,time,sys
root=Path(__file__).resolve().parents[2]
tools=Path.home()/'Documents/ch32-tools'
STEM='r1_ultrasonic_probe'
BASE_STEM='r1_motor_dashboard_no_knob'
BASELINE_PATH=None
out=root/'知行回路软件/build'/STEM
source=root/'知行回路软件/board'/STEM
ocd=tools/'MRS2/resources/app/resources/win32/components/WCH/OpenOCD/OpenOCD/bin'
work=tools/'ultrasonic-native-flash'
stamp=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y%m%d-%H%M%S')
rec={'date':stamp,'flash':'NOT_RUN','readback':'NOT_RUN','nonzero_motor_commands':'NONE','settings_writes':'NONE','commands':[]}

def main():
    if '--execute' not in sys.argv:
        print('Prepared only; no hardware access.');return
    meta=json.loads((out/'build_result.json').read_text(encoding='utf-8'))
    payload=(out/(STEM+'.bin')).read_bytes()
    assert hashlib.sha256(payload).hexdigest()==meta['binary_sha256']
    for name,digest in meta['all_source_sha256'].items():
        assert hashlib.sha256((source/name).read_bytes()).hexdigest()==digest,name
    baseline=(BASELINE_PATH or (root/'知行回路软件/build'/BASE_STEM/(BASE_STEM+'.bin'))).read_bytes()
    work.mkdir(exist_ok=True);out.mkdir(exist_ok=True)
    image=work/(stamp+'-program.bin');image.write_bytes(payload)
    backup=work/(stamp+'-before-full.bin')
    proc=None;link=None;written=False
    def command(cmd,timeout=8):
        link.settimeout(timeout);link.sendall(cmd.encode('utf-8')+b'\x1a');buf=b''
        while not buf.endswith(b'\x1a'):
            chunk=link.recv(65536)
            if not chunk:raise RuntimeError('Debugger disconnected')
            buf+=chunk
        response=buf[:-1].decode('utf-8',errors='replace')
        rec['commands'].append({'command':cmd,'reply':response})
        if response.startswith('error') or 'failed to write' in response.lower():raise RuntimeError(response)
        return response
    with (out/(stamp+'-openocd.log')).open('w',encoding='utf-8') as log:
        try:
            # Refuse an unrelated server instead of connecting to it.
            try:
                with socket.create_connection(('127.0.0.1',6666),timeout=.2):
                    raise RuntimeError('Debug server already running; stop before flashing')
            except OSError:pass
            proc=subprocess.Popen([str(ocd/'openocd.exe'),'-f','wch-riscv.cfg'],cwd=ocd,
                stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            for _ in range(50):
                if proc.poll() is not None:raise RuntimeError('OpenOCD exited; inspect log')
                try:link=socket.create_connection(('127.0.0.1',6666),timeout=.2);break
                except OSError:time.sleep(.2)
            if link is None:raise TimeoutError('WCH-Link unavailable')
            command('halt')
            command('dump_image {'+backup.as_posix()+'} 0 262144',45)
            original=backup.read_bytes()
            assert len(original)==262144
            saved=out/backup.name;saved.write_bytes(original)
            rec['backup']={'path':str(saved),'bytes':len(original),'sha256':hashlib.sha256(original).hexdigest()}
            assert original[:len(baseline)]==baseline,'Live baseline changed; no firmware write performed'
            command('reset halt');written=True
            rec['program_log']=command('capture {flash write_image erase {'+image.as_posix()+'} 0 bin}',45)
            verify=work/(stamp+'-readback.bin')
            command('dump_image {'+verify.as_posix()+'} 0 '+str(len(payload)),30)
            assert verify.read_bytes()==payload,'Firmware readback mismatch'
            (out/'live-readback.bin').write_bytes(verify.read_bytes())
            rec.update(flash='PASS',readback='PASS',binary_sha256=meta['binary_sha256'])
            command('reset halt');command('resume 0')
            rec['startup']='RESET_AND_RESUMED'
        except Exception as e:
            rec['error']=str(e)
            if written and link and backup.exists():
                try:
                    command('reset halt')
                    command('capture {flash write_image erase {'+backup.as_posix()+'} 0 bin}',45)
                    rollback=work/(stamp+'-rollback.bin')
                    command('dump_image {'+rollback.as_posix()+'} 0 262144',45)
                    assert rollback.read_bytes()==backup.read_bytes()
                    command('reset halt');command('resume 0');rec['rollback']='VERIFIED_ORIGINAL_RESTORED'
                except Exception as restore:rec['rollback_error']=str(restore)
            raise
        finally:
            if link:
                try:command('resume')
                except Exception:pass
                try:command('shutdown')
                except Exception:pass
                link.close()
            if proc and proc.poll() is None:
                try:proc.wait(timeout=3)
                except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=3)
            (out/'flash-verification.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in rec.items() if k!='commands'},ensure_ascii=False))
if __name__=='__main__':main()
