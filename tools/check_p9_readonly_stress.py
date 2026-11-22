"""Use the production serial implementation, read-only, with both outputs already zero."""
from pathlib import Path
import datetime,json,sys,time
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'知行回路软件/debug_ui'))
from speed_server import Bench,serial,list_ports
out=ROOT/'output/onboard_dashboard/gimbal-power-20261021'/('readonly-stress-'+datetime.datetime.now().strftime('%H%M%S'))
out.mkdir()
b=Bench(out);result=dict(test='PRODUCTION_P9_EXCHANGE_READONLY_STRESS',nonzero_or_actuator_commands=False,samples=[])
began=time.monotonic();error=None
try:
    ports=[p for p in list_ports.comports() if (p.vid,p.pid)==(0x1a86,0x8010)]
    if len(ports)!=1:raise RuntimeError('Expected exactly one P9; test not run')
    b.link=serial.Serial(ports[0].device,115200,timeout=.01,write_timeout=.15)
    b.identity=b.exchange('DRIVE_ID','DRIVE_ID,').split(',')[1]
    while time.monotonic()-began<20:
        b.snapshot();g=b.integration.gimbal_snapshot(b)
        row=dict(elapsed=time.monotonic()-began,gimbal=g,drive=b.latest['drive'],speeds=b.latest['wheel_speeds'],pwm=b.latest['applied_pwm'],uart_errors=b.latest['uart_errors'],uart_drops=b.latest['uart_drops'],mcu_ms=b.latest['raw']['drive'][0])
        result['samples'].append(row)
        if g['active'] or g['yaw_us'] or g['pitch_us'] or row['drive']['active'] or any(row['speeds']) or any(row['pwm']):raise RuntimeError('Unexpected active output; stop read-only check, no further command')
        if len(result['samples'])%10==0:
            result['registers']=b.numbers('GIMBAL_HW','GIMBAL_HW,',7)
            result['lease']=b.numbers('GIMBAL_RANDOM_STATUS','RANDOM,',5)
        time.sleep(.005)
    result['status']='READONLY_P9_STRESS_PASS; NOT_A_LOADED_GIMBAL_PASS'
except Exception as failure:
    result['status']='FAILED_OR_NOT_RUN';result['error']=str(failure);error=failure
finally:
    if b.link:b.link.close()
    b.raw.close()
    result['duration_s']=time.monotonic()-began
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(status=result['status'],samples=len(result['samples']),duration_s=result['duration_s'],evidence=str(out/'result.json')),ensure_ascii=False))
if error:raise SystemExit(1)
