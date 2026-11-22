"""Read-only MCU telemetry. No resets, debug attach, settings or motion writes."""
from pathlib import Path
import sys,json,time,datetime
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
import serial
from serial.tools import list_ports

def main():
    ports=[p for p in list_ports.comports() if p.vid==0x1A86]
    if len(ports)!=1:
        print(json.dumps({'serial_candidates':[{'port':p.device,'description':p.description} for p in ports]}))
        raise RuntimeError('Need one confirmed WCH serial port')
    rec={'date':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
         'firmware':'r1_ultrasonic_probe','motion_commands':'NONE','samples':[]}
    with serial.Serial(ports[0].device,115200,timeout=.15,write_timeout=1) as link:
        link.reset_input_buffer()
        def read(cmd,prefix):
            link.write((cmd+'\n').encode('ascii'));end=time.monotonic()+2
            while time.monotonic()<end:
                row=link.readline().decode('ascii',errors='replace').strip()
                if row.startswith(prefix):return row
            raise TimeoutError('No response to '+cmd)
        rec['ping']=read('PING','PONG')
        for _ in range(10):
            row=read('ULTRA_STATUS','ULTRA,')
            keys=('ms','valid','status','distance_mm','pulse_us','triggers','good','timeouts','edges','rejected','age_ms','timer_hz')
            values=[int(v) for v in row.split(',')[1:]]
            assert len(values)==len(keys)
            rec['samples'].append(dict(zip(keys,values)));time.sleep(.2)
        rec['tof_status']=read('STATUS','STATUS,')
        rec['screens']={cmd:read(cmd,prefix) for cmd,prefix in [('OLED_SCREEN','SCREEN,'),('OLED2_SCREEN','SCREEN2,'),('OLED3_SCREEN','SCREEN3,')]}
    rec['valid_samples']=sum(s['valid']==1 and s['status']==1 for s in rec['samples'])
    rec['distance_mm']=[s['distance_mm'] for s in rec['samples'] if s['valid']==1 and s['status']==1]
    rec['accuracy']='NOT_CALIBRATED'
    out=root/'知行回路软件/build/r1_ultrasonic_probe';out.mkdir(exist_ok=True)
    name=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y%m%d-%H%M%S')+'-telemetry.json'
    (out/name).write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(rec,ensure_ascii=False))
    print('Evidence:',out/name)
if __name__=='__main__':main()
