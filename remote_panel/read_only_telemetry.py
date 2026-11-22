"""Temporary PC-to-phone read-only telemetry bridge. No motion/write commands."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone
from urllib.parse import urlsplit
import argparse, json, secrets, sys, threading, time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(Path.home()/'Documents/ch32-tools/python-support'))
import serial

# Explicit immutable allowlist. No route forwards client input to the UART.
READS=(('STATUS','STATUS,',11),('MOTOR_DASH_STATUS','MOTORDASH,',14),
       ('RECOVERY_STATUS','RECOVERY,',9),('PARAM_STATUS','PARAM,',4),
       ('MUTE_STATUS','MUTE,',5),('MOTOR_STATUS','MOTOR,',7))
lock=threading.Lock()
latest={'connected':False,'error':'等待主控数据','received_monotonic':0}
stop=threading.Event()

def decode(rows):
    s,d,r,p,m,h=(rows[x[0]] for x in READS)
    range_ok=s[2]==0 and s[3]==0 and r[0]==0 and r[4]==0 and r[5]!=3
    return {'connected':True,'error':None,'received_monotonic':time.monotonic(),
        'received_at':datetime.now(timezone.utc).isoformat(),'uptime_s':s[0]//1000,
        'range_rounds':s[1],'distance_mm':s[4] if range_ok else None,'range_valid':range_ok,
        'guard_state':r[5],'voltage_mv':d[1] if d[2] else None,
        'driver_state':d[10],'wheel_speeds_mm_s':d[5:9] if d[4] else None,
        'motion_active':bool(d[9]),'motor_fault':d[11],
        'warning_mm':p[0],'muted':bool(m[0]),'uart_errors':h[1],'uart_drops':h[2],
        'serial_source':'CH32 UART','mode':'READ_ONLY'}

def public_state(now=None):
    with lock: data=dict(latest)
    now=time.monotonic() if now is None else now
    age=now-data.pop('received_monotonic',0)
    data['age_ms']=round(age*1000) if age<86400 else None
    if not data.get('connected') or age>5:
        data['connected']=False
        data['distance_mm']=data['voltage_mv']=data['wheel_speeds_mm_s']=None
        data['uptime_s']=data['warning_mm']=data['muted']=None
        data['driver_state']=data['guard_state']=None
        data['motion_active']=data['motor_fault']=None
        data['uart_errors']=data['uart_drops']=None
        data['range_valid']=False
        data['error']=data.get('error') or '数据已过期'
    return data

def worker(port):
    global latest
    while not stop.is_set():
        try:
            with serial.Serial(port,115200,timeout=.1,write_timeout=1) as link:
                while not stop.is_set():
                    rows={}
                    for cmd,prefix,count in READS:
                        link.write(cmd.encode('ascii')+b'\n')
                        deadline=time.monotonic()+2
                        while time.monotonic()<deadline and not stop.is_set():
                            line=link.readline().decode('ascii',errors='replace').strip()
                            if not line.startswith(prefix):continue
                            values=[int(x) for x in line.split(',')[1:]]
                            if len(values)!=count:raise ValueError('状态格式不符：'+cmd)
                            rows[cmd]=values;break
                        else:raise TimeoutError('主控未回复：'+cmd)
                    if stop.is_set():break
                    data=decode(rows)
                    with lock:latest=data
                    (HERE/'telemetry.json').write_text(json.dumps(public_state(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                    stop.wait(.5)
        except Exception as e:
            with lock:latest={**latest,'connected':False,'error':str(e)}
            stop.wait(2)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--serial',default='COM5');ap.add_argument('--bind',default='127.0.0.1')
    ap.add_argument('--port',type=int,default=8766)
    args=ap.parse_args();token=secrets.token_urlsafe(18);base='/'+token
    class Handler(BaseHTTPRequestHandler):
        def send(self,code,content,kind):
            self.send_response(code);self.send_header('Content-Type',kind)
            self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(content)))
            self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(content)
        def do_GET(self):
            path=urlsplit(self.path).path
            if path in (base,base+'/'):
                self.send(200,(HERE/'index.html').read_bytes(),'text/html; charset=utf-8')
            elif path==base+'/api/status':
                self.send(200,json.dumps(public_state(),ensure_ascii=False).encode('utf-8'),'application/json; charset=utf-8')
            else:self.send(404,b'Not found','text/plain')
        def do_POST(self):self.send(405,b'Read only','text/plain')
        def log_message(self,*args):pass
    server=ThreadingHTTPServer((args.bind,args.port),Handler)
    runtime={'pid':__import__('os').getpid(),'serial':args.serial,'bind':args.bind,'port':args.port,
             'url':f'http://{args.bind}:{args.port}{base}/','mode':'READ_ONLY_PC_RELAY',
             'started_at':datetime.now(timezone.utc).isoformat()}
    (HERE/'runtime.json').write_text(json.dumps(runtime,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    threading.Thread(target=worker,args=(args.serial,),daemon=True).start()
    print(json.dumps(runtime,ensure_ascii=False),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:stop.set();server.server_close()
if __name__=='__main__':main()
