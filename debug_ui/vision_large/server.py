"""Read-only vision bridge. Serves the shared UI panel; never opens P7/P9.

Phone browsers may send one camera snapshot to this PC. Optional --source-url
is a read-only proxy to the existing phone gateway for the desktop panel.
"""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler
import argparse
import base64
import datetime
import hashlib
import io
import ipaddress
import json
import mimetypes
import os
import re
import secrets
import threading
import time
from PIL import Image
import model

HERE = Path(__file__).resolve().parent
UI = HERE.parent
DEFAULT_QUESTION = '请描述画面中有哪些主要物体、颜色和相对位置；看不清的地方请明确说明。'


def local_source(value):
    if not value:
        return None
    p = urlsplit(value)
    if p.scheme != 'http' or p.username or p.password or p.query or p.fragment:
        raise ValueError('相机源必须是已有本机或局域网HTTP服务')
    host = p.hostname
    if host != 'localhost':
        a = ipaddress.ip_address(host)
        if not (a.is_loopback or a.is_private) or a.is_unspecified or a.is_link_local:
            raise ValueError('相机源不在本机/局域网')
    return value.rstrip('/')


def valid_origin(value):
    try:
        p = urlsplit(value)
        if p.scheme != 'http' or p.username or p.password or p.path or p.query or p.fragment:
            return False
        if p.hostname == 'localhost':
            return True
        a = ipaddress.ip_address(p.hostname)
        return (a.is_loopback or a.is_private) and not (a.is_unspecified or a.is_link_local)
    except (ValueError, TypeError):
        return False


def validate_image(encoded):
    if not isinstance(encoded, str) or len(encoded) > 3_000_000:
        raise ValueError('图片超过限制，请使用相机标准清晰度或较小照片')
    try:
        raw = base64.b64decode(encoded, validate=True)
        if not raw or len(raw) > 2_000_000:
            raise ValueError()
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in ('JPEG', 'PNG') or image.width * image.height > 12_000_000:
                raise ValueError()
            image.verify()
    except Exception:
        raise ValueError('需要有效JPEG或PNG，最大2MB/1200万像素') from None
    return raw


class Jobs:
    def __init__(self, folder):
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.active = None
        self.jobs = {}

    def get(self, ident):
        with self.lock:
            if ident not in self.jobs:
                return None
            return dict(self.jobs[ident])

    def submit(self, body):
        if set(body)-{'image_base64', 'question', 'input_source', 'frame_seq', 'captured_at'}:
            raise ValueError('识别请求字段错误')
        question = body.get('question', DEFAULT_QUESTION)
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 600:
            raise ValueError('问题需要1—600字')
        source = body.get('input_source')
        if source not in ('camera_snapshot', 'selected_photo', 'synthetic_test'):
            raise ValueError('图片来源未说明')
        raw = validate_image(body.get('image_base64'))
        seq = str(body.get('frame_seq', ''))[:40]
        captured = body.get('captured_at')
        # Snapshot age is explicit; never advertise a delayed answer as live state.
        if not isinstance(captured, str) or len(captured) > 50:
            raise ValueError('图片时间缺失')
        try:
            when = datetime.datetime.fromisoformat(captured.replace('Z', '+00:00'))
            age = datetime.datetime.now(datetime.timezone.utc)-when
            if source == 'camera_snapshot' and not -5 <= age.total_seconds() <= 10:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError('相机快照已过期，请重新取图；同时核对设备时间') from None
        with self.lock:
            if self.active:
                raise RuntimeError('大模型正在分析上一张图片，请稍后再试')
            ident = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-')+secrets.token_hex(4)
            item = {'id': ident, 'state': 'running', 'question': question.strip(),
                    'model': model.MODEL, 'deployment': 'computer_local_ollama',
                    'input_source': source, 'captured_at': captured, 'frame_seq': seq,
                    'submitted_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'image_sha256': hashlib.sha256(raw).hexdigest(), 'actuation_enabled': False}
            (self.folder/(ident+'.image')).write_bytes(raw)
            (self.folder/(ident+'.json')).write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding='utf-8')
            self.jobs[ident] = item
            self.active = ident
        threading.Thread(target=self.run, args=(ident, raw), daemon=True).start()
        return dict(item)

    def run(self, ident, raw):
        try:
            result = model.recognize(raw, self.jobs[ident]['question'])
            update = {**result, 'state': 'done'}
        except Exception as error:
            update = {'state': 'failed', 'error': '本次识别失败：'+str(error)[:300]}
        with self.lock:
            self.jobs[ident].update(update, completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
            (self.folder/(ident+'.json')).write_text(json.dumps(self.jobs[ident], ensure_ascii=False, indent=2), encoding='utf-8')
            self.active = None
            # Evidence persists on disk; bound in-memory session history.
            while len(self.jobs) > 50:
                del self.jobs[next(iter(self.jobs))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8797)
    parser.add_argument('--source-url')
    parser.add_argument('--output', type=Path, default=UI.parents[1]/'output/onboard_dashboard/large-vision-20261107')
    args = parser.parse_args()
    source = local_source(args.source_url)
    args.output.mkdir(parents=True, exist_ok=True)
    runtime_file = args.output/'runtime.json'
    try:
        base = json.loads(runtime_file.read_text(encoding='utf-8'))['base']
        if not re.fullmatch('/[A-Za-z0-9_-]{24,64}', base):
            raise ValueError()
    except (OSError, ValueError, KeyError):
        base = '/'+secrets.token_urlsafe(24)
    jobs = Jobs(args.output/'events')

    class Handler(BaseHTTPRequestHandler):
        def origin_ok(self):
            return valid_origin(self.headers.get('Origin', ''))

        def send(self, code, value, kind='application/json; charset=utf-8'):
            raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            if self.origin_ok():
                self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
                self.send_header('Vary', 'Origin')
            self.end_headers()
            self.wfile.write(raw)

        def do_OPTIONS(self):
            if not self.path.startswith(base+'/api/') or not self.origin_ok():
                self.send(403, {'error': '请从本机或局域网调试网页访问'})
                return
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.send_header('Vary', 'Origin')
            self.send_header('Content-Length', '0')
            self.end_headers()

        def do_GET(self):
            path = urlsplit(self.path).path
            if path in (base+'/', base):
                doc = (HERE/'panel.html').read_text(encoding='utf-8').replace('__BASE__', base)
                self.send(200, doc.encode('utf-8'), 'text/html; charset=utf-8')
                return
            if path.startswith(base+'/assets/'):
                target = (UI/path[len(base+'/'):]).resolve()
                if not target.is_relative_to((UI/'assets').resolve()) or not target.is_file():
                    self.send(404, {'error': '文件不存在'})
                    return
                kind = 'text/javascript' if target.suffix == '.js' else mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
                self.send(200, target.read_bytes(), kind+'; charset=utf-8')
                return
            if not path.startswith(base+'/api/'):
                self.send(404, {'error': '请使用启动时显示的完整地址'})
                return
            route = path[len(base+'/api/'):]
            if route == 'vlm/status':
                self.send(200, {**model.status(), 'busy': bool(jobs.active)})
            elif re.fullmatch('vlm/job/[0-9]{8}-[0-9]{6}-[a-f0-9]{8}', route):
                item = jobs.get(route.split('/')[-1])
                self.send(200 if item else 404, item or {'error': '本次会话没有该结果'})
            elif route in ('camera/status', 'camera/frame', 'ui/info'):
                if route == 'ui/info':
                    self.send(200, {'demo': False, 'platform': 'VLM_BRIDGE', 'large_vision': True})
                elif not source:
                    self.send(503, {'error': '尚未连接车载相机；可选择照片分析，或重启时指定车载网页地址'})
                else:
                    try:
                        with build_opener(ProxyHandler({})).open(source+'/api/'+route, timeout=3) as r:
                            raw = r.read(2_000_001)
                            if len(raw) > 2_000_000:
                                raise ValueError('图片过大')
                            self.send(r.status, raw, r.headers.get('Content-Type', 'application/json'))
                    except Exception:
                        self.send(503, {'error': '车载相机未连接或没有新鲜画面，请检查手机画面'})
            else:
                self.send(404, {'error': '此服务只提供看图，不提供车辆控制'})

        def do_POST(self):
            if urlsplit(self.path).path != base+'/api/vlm/analyze':
                self.send(404, {'error': '此服务只提供看图，不提供车辆控制'})
                return
            if not self.origin_ok() or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                self.send(403, {'error': '请从当前调试网页提交图片'})
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 3_100_000:
                    raise ValueError('图片请求过大')
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError('请求格式错误')
                self.send(202, jobs.submit(body))
            except (ValueError, TypeError) as error:
                self.send(400, {'error': str(error)})
            except RuntimeError as error:
                self.send(409, {'error': str(error)})

        def log_message(self, *_):
            pass

    class Server(ThreadingHTTPServer):
        allow_reuse_address = False
        daemon_threads = True

    server = Server((args.bind, args.port), Handler)
    runtime = {'pid': os.getpid(), 'port': args.port, 'bind': args.bind, 'base': base,
               'url': f'http://127.0.0.1:{args.port}{base}/', 'model': model.MODEL,
               'deployment': 'computer_local_ollama', 'camera_proxy_configured': bool(source),
               'actuation_enabled': False}
    runtime_file.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(runtime, ensure_ascii=False), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
