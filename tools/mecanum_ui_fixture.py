"""Local browser fixture. Serves UI files; fake API stays entirely in browser."""
from pathlib import Path
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
SW=Path(__file__).resolve().parents[1];UI=SW/'debug_ui_mecanum'
BOOT=b'''import {createDrive} from './assets/features/drive.js';
const fixture=window.fixture={requests:[],active:false,mecanum:true};
const api={async post(path,body){fixture.requests.push({path,body});if(path==='drive/start'){fixture.active=true;return {session:'OFFLINE_FIXTURE'};}if(path==='drive/stop'){fixture.active=false;return {stopped:true};}return {ok:true,braked:true};},beacon(path){fixture.requests.push({path,beacon:true});fixture.active=false;}};
const drive=createDrive(api);fixture.drive=drive;
fixture.render=()=>drive.render({connected:true,age_ms:0,control_model:'driver_native_speed',drive:{active:fixture.active},capabilities:{drive_control:true,mecanum_control:fixture.mecanum,driver_speed_limit:1000},speed_targets:[100,-100,-100,100],speed_commands:[60,-60,-60,60]});
fixture.render();setInterval(fixture.render,300);document.documentElement.dataset.uiReady='true';
document.getElementById('driveTools').open=true;
document.getElementById('demoNotice').hidden=false;
document.getElementById('demoNotice').textContent='OFFLINE FIXTURE / local browser test only';
'''
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kw):super().__init__(*args,directory=str(UI),**kw)
    def do_GET(self):
        if self.path=='/fixture.js':data=BOOT;mime='text/javascript'
        elif self.path in ('/','/index.html'):
            data=(UI/'index.html').read_bytes().replace(b'assets/app.js',b'fixture.js');mime='text/html; charset=utf-8'
        else:return super().do_GET()
        self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def log_message(self,*args):pass
if __name__=='__main__':
    import sys
    if '--current' in sys.argv:UI=SW/'debug_ui'
    print('OFFLINE UI fixture http://127.0.0.1:8898',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8898),Handler).serve_forever()
