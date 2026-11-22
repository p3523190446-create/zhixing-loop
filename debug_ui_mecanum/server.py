"""Desktop/mobile UI host. Proxies the existing backend; never opens a serial port."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import argparse, json, mimetypes, os, re, secrets

HERE = Path(__file__).resolve().parent
BACKEND_RUNTIME = HERE.parent / 'remote_panel/runtime.json'
READS = {'status', 'camera/status', 'camera/frame', 'record/status', 'record/list', 'photo/list'}
WRITES = {'gimbal/' + s for s in ('start', 'set', 'center', 'heartbeat', 'stop')} | {'camera/start', 'camera/stop', 'record/start', 'record/stop', 'photo/capture'} | {'drive/' + s for s in ('start', 'set', 'brake', 'stop')}

def allowed_read(path):
    return path in READS or bool(re.fullmatch(r'record/[0-9]{8}-[0-9]{6}-[0-9a-f]{6}/(data|frame|video|download)', path)) or bool(re.fullmatch(r'photo/[0-9]{8}-[0-9]{6}-[0-9a-f]{6}/(image|download)', path))

def backend():
    runtime = json.loads(BACKEND_RUNTIME.read_text(encoding='utf-8'))
    url = urlsplit(runtime['url'])
    if url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost'):
        raise ValueError('仅允许连接本机现有调试服务')
    return runtime['url'].rstrip('/'), 'http://' + url.netloc

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8772)
    parser.add_argument('--demo', action='store_true', help='Explicit simulated mode, never accesses backend or hardware')
    args = parser.parse_args()
    base = '/' + secrets.token_urlsafe(18)
    if args.demo:
        from demo_backend import DemoBackend
        demo = DemoBackend()
    else:
        demo = None
    class Handler(BaseHTTPRequestHandler):
        def send(self, code, content, kind='application/json; charset=utf-8', seq=None):
            if not isinstance(content, bytes): content = json.dumps(content, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if seq is not None: self.send_header('X-Frame-Seq', str(seq))
            self.end_headers()
            self.wfile.write(content)
        def api(self, method):
            parsed = urlsplit(self.path)
            path = parsed.path[len(base + '/api/'):]
            if method == 'GET' and path == 'ui/info':
                self.send(200, {'demo': args.demo, 'vehicle_motion':'DISABLED', 'source':'simulated' if args.demo else 'existing local backend'})
                return
            if not (allowed_read(path) if method == 'GET' else path in WRITES or args.demo and path == 'demo/scenario'):
                self.send(404, {'error':'没有这个调试接口'})
                return
            content = None
            if method == 'POST':
                if self.headers.get('Origin') != 'http://' + self.headers.get('Host','') or self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                    self.send(403, {'error':'请从当前调试页面操作'})
                    return
                try:
                    size = int(self.headers.get('Content-Length','0'))
                    if not 0 < size <= 512: raise ValueError()
                    content = self.rfile.read(size)
                    body = json.loads(content)
                    if not isinstance(body, dict): raise ValueError()
                except (ValueError, TypeError):
                    self.send(400, {'error':'请求格式错误'})
                    return
            try:
                if demo is not None:
                    code, value, kind, seq = demo.request(method, path, parsed.query, json.loads(content) if content else {})
                    self.send(code, value, kind, seq)
                    return
                target, origin = backend()
                headers = {'Origin': origin, 'Content-Type':'application/json'} if method == 'POST' else {}
                request = Request(target + '/api/' + path + ('?' + parsed.query if parsed.query else ''), data=content, headers=headers, method=method)
                try:
                    response = urlopen(request, timeout=9)
                except HTTPError as error:
                    response = error
                with response:
                    self.send(response.status, response.read(), response.headers.get('Content-Type','application/json'), response.headers.get('X-Frame-Seq'))
            except (OSError, URLError, ValueError, KeyError) as error:
                self.send(503, {'error':'现有主控服务未连接，请先恢复电脑链路。'})
        def do_GET(self):
            path = urlsplit(self.path).path
            if args.demo and path in ('/', '/desktop', '/ipad-preview'):
                destination = base + ('/assets/ipad-preview.html' if path == '/ipad-preview' else '/desktop')
                self.send_response(302)
                self.send_header('Location', destination)
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', '0')
                self.end_headers()
            elif path.startswith(base + '/api/'):
                self.api('GET')
            elif path in (base, base+'/', base+'/desktop', base+'/mobile'):
                document = (HERE/'index.html').read_text(encoding='utf-8')
                # Absolute assets make /desktop and /mobile share exactly the same modules.
                document = document.replace('href="assets/', 'href="'+base+'/assets/').replace('src="assets/', 'src="'+base+'/assets/')
                document = document.replace('<body>', '<body data-base="'+base+'">')
                if args.demo: document = document.replace('id="demoNotice" class="notice demo" hidden','id="demoNotice" class="notice demo"')
                document = document.replace('href="desktop"','href="'+base+'/desktop"').replace('href="mobile"','href="'+base+'/mobile"').replace('href="./"','href="'+base+'/"')
                self.send(200,document.encode('utf-8'),'text/html; charset=utf-8')
            elif path.startswith(base+'/assets/'):
                relative = path[len(base+'/'):]
                target = (HERE/relative).resolve()
                if not target.is_relative_to((HERE/'assets').resolve()) or not target.is_file():
                    self.send(404, {'error':'文件不存在'})
                    return
                kind = 'text/javascript' if target.suffix == '.js' else mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
                self.send(200,target.read_bytes(),kind+'; charset=utf-8')
            else:
                self.send(404,{'error':'页面不存在，请使用runtime.json中的完整地址'})
        def do_POST(self):
            if self.path.startswith(base+'/api/'): self.api('POST')
            else: self.send(404,{'error':'接口不存在'})
        def log_message(self, *_): pass
    class UniqueServer(ThreadingHTTPServer):
        allow_reuse_address = False
    server = UniqueServer((args.bind,args.port),Handler)
    server.daemon_threads = True
    runtime={'pid':os.getpid(),'bind':args.bind,'port':args.port,'base':base,'demo':args.demo,
             'url':f'http://127.0.0.1:{args.port}{base}/','desktop':f'http://127.0.0.1:{args.port}{base}/desktop','mobile':f'http://127.0.0.1:{args.port}{base}/mobile'}
    (HERE/('demo-runtime.json' if args.demo else 'runtime.json')).write_text(json.dumps(runtime,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(runtime,ensure_ascii=False),flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__ == '__main__': main()
