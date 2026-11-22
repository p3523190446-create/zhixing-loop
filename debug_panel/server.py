"""Local read-only observer. Never opens serial ports or invokes hardware tools."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone
from urllib.parse import urlsplit
import argparse
import json
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VISION = ROOT / 'output/phone_vision'
BUILD = ROOT / '知行回路软件/build'
PROJECT = ROOT / '比赛备案/项目状态.json'

def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return None

def stamp(path):
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    except OSError:
        return None

def age_of(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            return None
        age = time.time() - parsed.timestamp()
        return None if age < -5 else max(0, age)
    except (ValueError, TypeError, AttributeError):
        return None

def log_tail(path):
    try:
        with path.open('rb') as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - 18000))
            text = stream.read().decode('utf-8', errors='replace')
        return '\n'.join(text.splitlines()[-100:])
    except OSError:
        return ''

def detection(row, labels):
    if not isinstance(row, dict):
        return None
    try:
        parts = str(row.get('ack', '')).split(',')
        if len(parts) < 6 or parts[0] != 'ACK':
            return None
        cls = int(parts[2])
        score = int(parts[3]) / 1000
        if cls != 255 and (not 0 <= cls < 80 or not 0 <= score <= 1):
            return None
        return {'at': row.get('at'), 'seq': row.get('phone_seq'),
                'class_id': cls, 'empty': cls == 255,
                'label': '未检测到目标' if cls == 255 else (labels[cls] if 0 <= cls < len(labels) else f'类别 {cls}'),
                'score': score if cls != 255 else None,
                'cx': int(parts[4]) / 1000, 'cy': int(parts[5]) / 1000,
                'age_seconds': age_of(row.get('at'))}
    except (ValueError, TypeError, IndexError):
        return None

def snapshot():
    status_path = VISION / 'monitor-status.json'
    monitor = read_json(status_path)
    monitor = monitor if isinstance(monitor, dict) else {}
    age = age_of(monitor.get('updated_at'))
    fresh = age is not None and age <= 5 and monitor.get('running') is True
    allowed = ['running', 'updated_at', 'board_connected', 'phone_connected',
               'app_process_running', 'phone_state', 'last_frame_age_seconds',
               'last_ack_age_seconds', 'frames_acked', 'heartbeats_acked', 'board_connections',
               'last_error', 'usb_authorization_pending', 'stopped_reason', 'uptime_seconds']
    selected = {k: monitor.get(k) for k in allowed}
    selected.update(available=bool(monitor), fresh=fresh, age_seconds=age,
                    source='output/phone_vision/monitor-status.json')
    rows = read_json(VISION / 'monitor-recent-frames.json')
    labels = read_json(ROOT / '知行回路软件/phone_vision/coco-labels-cn.json')
    labels = [item.get('cn', item.get('en', '未知类别')) if isinstance(item, dict) else str(item)
              for item in labels] if isinstance(labels, list) else []
    targets = [item for row in (rows[-20:] if isinstance(rows, list) else [])
               if (item := detection(row, labels)) is not None]
    project = read_json(PROJECT) or {}
    registered = project.get('latest_live_firmware', {})
    fw_name = registered.get('name', '未知')
    # Only read registered firmware evidence; never label its old snapshots live.
    fw_dir = BUILD / fw_name if fw_name in [p.name for p in BUILD.iterdir() if p.is_dir()] else BUILD / '_missing'
    verification = read_json(fw_dir / 'flash-display-verification.json') or {}
    layout = read_json(fw_dir / 'layout-verification.json') or {}
    build = read_json(fw_dir / 'build_result.json') or {}
    fw = {'name': fw_name, 'flash': verification.get('flash'), 'readback': verification.get('readback'),
          'uart': verification.get('uart'), 'compile': layout.get('compile', build.get('status')),
          'at': stamp(fw_dir / 'flash-display-verification.json'),
          'motor_control': registered.get('motion_control', False),
          'physical_acceptance': layout.get('physical_layout'),
          'distance_snapshot_mm': verification.get('boot_status', {}).get('range_corrected_mm'),
          'screen1': layout.get('screen1'), 'screen2': layout.get('screen2'), 'screen3': layout.get('screen3')}
    logs = [{'id': key, 'name': label, 'updated_at': stamp(path), 'text': log_tail(path)}
            for key, label, path in [
                ('bridge', '手机转发日志', VISION / 'monitor-stdout.log'),
                ('errors', '转发错误日志', VISION / 'monitor-stderr.log'),
                ('openocd', '下载连接 · OpenOCD', fw_dir / 'openocd-display.log'),
                ('gdb', '变量与读回 · GDB', fw_dir / 'gdb-display.log')]]
    return {'server_time': datetime.now(timezone.utc).isoformat(), 'read_only': True,
            'monitor': selected, 'targets': targets, 'firmware': fw, 'logs': logs,
            'events': (monitor.get('events') or [])[-20:],
            'telemetry': {'distance_live_available': False, 'warning_live_available': False}}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/status':
            try:
                payload = json.dumps(snapshot(), ensure_ascii=False).encode('utf-8')
            except Exception:
                self.reply(503, b'{"error":"snapshot_unavailable"}', 'application/json')
                return
            self.reply(200, payload, 'application/json; charset=utf-8')
        elif path in ('/', '/index.html'):
            self.reply(200, (HERE / 'index.html').read_bytes(), 'text/html; charset=utf-8')
        elif path == '/favicon.ico':
            self.reply(204, b'', 'image/x-icon')
        else:
            self.reply(404, b'Not found', 'text/plain')

    def reply(self, code, payload, content_type):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):
        pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    for port in range(args.port, args.port + 20):
        try:
            server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
            break
        except OSError:
            continue
    else:
        raise SystemExit('No free local port')
    info = {'url': f'http://127.0.0.1:{port}/', 'read_only': True}
    (HERE / 'runtime.json').write_text(json.dumps(info), encoding='utf-8')
    print(info['url'], flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
