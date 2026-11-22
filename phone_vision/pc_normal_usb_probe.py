"""Normal-feature read-only proof; no movement or persistent writes.
Default P7 native CDC. --wch checks restored P9 UART separately.
"""
from pathlib import Path
import sys,json,base64,time,datetime
sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
import serial
from serial.tools import list_ports
root=Path(__file__).resolve().parents[2]
native='--wch' not in sys.argv
ports=[p for p in list_ports.comports() if p.vid==0x1a86 and p.pid==(0xfe0c if native else 0x8010)]
folder=root/'output/phone_board_link'/('pc-normal-'+('usbfs-' if native else 'wch-')+time.strftime('%Y%m%d-%H%M%S'));folder.mkdir(parents=True)
events=[];replies=[];error=None
def raw(kind,data):
    events.append(dict(seq=len(events)+1,monotonic_ns=time.monotonic_ns(),direction=kind,length=len(data),data_b64=base64.b64encode(data).decode()))
formats={'STATUS':('STATUS',11),'GIMBAL_STATUS':('GIMBAL',10),'ULTRA_STATUS':('ULTRA',12),
    'OLED_SCREEN':('SCREEN',3),'OLED2_SCREEN':('SCREEN2',3),'OLED3_SCREEN':('SCREEN3',3),
    'OLED_STATUS':('OLED',5),'OLED2_STATUS':('OLED2',5),'OLED3_STATUS':('OLED3',5),
    'MUTE_STATUS':('MUTE',5),'SETTINGS_STATUS':('SETTINGS',11),'RECOVERY_STATUS':('RECOVERY',9),
    'PARAM_STATUS':('PARAM',4),'MOTOR_DASH_STATUS':('MOTORDASH',14)}
def query(conn,command):
    tx=(command+'\n').encode('ascii');raw('TX_ATTEMPT',tx)
    n=conn.write(tx);raw('TX_ACCEPTED',tx[:n]);conn.flush()
    if n!=len(tx):raise RuntimeError('Partial write')
    result=bytearray();deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        chunk=conn.read(64)
        if chunk:raw('RX',chunk);result.extend(chunk)
        if b'\n' in result:break
    if not result.endswith(b'\n') or result.count(b'\n')!=1:raise RuntimeError('Missing/extra reply for '+command)
    line=result[:-1].decode('ascii');fields=line.split(',')
    if command=='PING':assert line=='PONG'
    elif command=='NATIVE_FEATURES':assert line=='NORMAL_USBFS,1'
    elif command=='UNSUPPORTED_TEST':assert line=='ERR,USB_READ_ONLY'
    else:
        prefix,count=formats[command];assert fields[0]==prefix and len(fields)==count+1,(command,line)
        for value in fields[1:]:int(value)
    item={'command':command,'line':line,'fields':fields[1:],'bytes':len(result)};replies.append(item);return item
try:
    if len(ports)!=1:raise RuntimeError('Expected unique target serial port; found '+str(len(ports)))
    with serial.Serial(ports[0].device,115200,timeout=.15,write_timeout=1) as conn:
        conn.reset_input_buffer()
        if native:query(conn,'NATIVE_FEATURES')
        for repeat in range(3):
            for command in ('PING','STATUS','GIMBAL_STATUS','ULTRA_STATUS'):query(conn,command)
        screen_before={command:query(conn,command) for command in ('OLED_SCREEN','OLED2_SCREEN','OLED3_SCREEN')}
        for command in ('OLED_STATUS','OLED2_STATUS','OLED3_STATUS','MUTE_STATUS','SETTINGS_STATUS','RECOVERY_STATUS','PARAM_STATUS','MOTOR_DASH_STATUS'):query(conn,command)
        if native:query(conn,'UNSUPPORTED_TEST')
        screen_after={command:query(conn,command) for command in screen_before}
        times=[int(x['fields'][0]) for x in replies if x['command']=='STATUS']
        assert all(a<b for a,b in zip(times,times[1:])), 'Main uptime not advancing'
        for x in replies:
            if x['command']=='GIMBAL_STATUS':assert int(x['fields'][2])==0 and x['fields'][4:6]==['0','0'], 'Unexpected gimbal PWM'
        for command in screen_before:
            before=screen_before[command]['fields'];after=screen_after[command]['fields']
            assert after[1]=='1' and after[2]=='0' and int(after[0])>int(before[0]), ('Screen not refreshed',command,before,after)
except Exception as exc:error=repr(exc)
result=dict(at=datetime.datetime.now().astimezone().isoformat(),mode='PC_NORMAL_USBFS' if native else 'PC_NORMAL_WCH',
    port=ports[0].device if len(ports)==1 else None,passed=error is None,replies=replies,error=error,motion_commands_sent=False,
    scope='Communication, increasing uptime, zero servo PWM, three OLED frame counters; target accuracy and physical LEDs not certified')
(folder/'bytes.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events),encoding='utf-8')
(folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'folder':str(folder),**result},ensure_ascii=False))
raise SystemExit(0 if result['passed'] else 1)
