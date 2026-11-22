"""Bounded live desktop vision experiments. No board or actuator writes.

Real camera observations and generated/replayed checks are saved separately.
Only /api/tracking/config may be posted; the previous mode is restored.
"""
import bootstrap
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime
import json
from pathlib import Path
import statistics
import time
import urllib.request

HERE = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:8796'
OUT = bootstrap.ROOT / 'output/onboard_dashboard/algorithm-experiments-20261026'


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=6) as response:
        return json.load(response)


def config(mode, enabled=True):
    request = urllib.request.Request(BASE + '/api/tracking/config',
        data=json.dumps(dict(mode=mode, enabled=enabled)).encode(),
        headers={'Origin': BASE, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=6) as response:
        result = json.load(response)
    if result.get('actuation_enabled') is not False:
        raise RuntimeError('Expected calculation-only configuration')


def stats(values):
    data = sorted(values)
    return dict(median=statistics.median(data), p95=data[min(len(data)-1, int(len(data)*.95))],
                minimum=data[0], maximum=data[-1]) if data else None


def stream(endpoint, folder, count=121):
    rows = []
    started = time.monotonic()
    with urllib.request.urlopen(BASE + '/' + endpoint, timeout=8) as response:
        boundary = response.readline()
        while len(rows) < count:
            if time.monotonic()-started > 20:
                raise TimeoutError('Bounded stream measurement exceeded 20 seconds')
            if boundary.strip() != b'--zhixingframe':
                raise ValueError('Unexpected stream boundary')
            headers = {}
            while True:
                line = response.readline()
                if line == b'\r\n':
                    break
                key, value = line.decode('ascii').split(':', 1)
                headers[key.lower()] = value.strip()
            size = int(headers['content-length'])
            if not 0 < size <= 4*1024*1024:
                raise ValueError('Unexpected frame size')
            frame = response.read(size)
            now = time.monotonic()
            if len(frame) != size or not frame.startswith(b'\xff\xd8') or not frame.endswith(b'\xff\xd9'):
                raise ValueError('Invalid live JPEG')
            if not rows:
                (folder / (endpoint.replace('.mjpeg', '') + '-first.jpg')).write_bytes(frame)
            rows.append(dict(seq=headers['x-frame-seq'], at=now, bytes=size,
                host_age_ms=(now-int(headers['x-source-received-ns'])/1e9)*1000))
            if response.read(2) != b'\r\n':
                raise ValueError('Unexpected frame delimiter')
            boundary = response.readline()
    duration = rows[-1]['at']-rows[0]['at']
    return dict(frames=len(rows), unique_sequences=len(set(row['seq'] for row in rows)),
                duration_s=duration, fps=(len(rows)-1)/duration,
                host_age_ms=stats([r['host_age_ms'] for r in rows]), samples=rows,
                clock_resolution_ms=time.get_clock_info('monotonic').resolution*1000,
                zero_age_is_not_zero_latency=True,
                age_definition='PC capture-thread JPEG publication to local client receipt; excludes exposure and USB acquisition delay')


def observe_mode(mode, folder):
    config(mode)
    started = time.monotonic()
    seen = set()
    rows = []
    while time.monotonic()-started < 12:
        d = get('/api/status')
        tracking = d.get('tracking') or {}
        vision = d.get('vision') or {}
        seq = d.get('frame_seq')
        if (d.get('vision_valid') and tracking.get('mode') == mode and seq is not None
                and seq not in seen and (mode != 'face' or vision.get('face_enabled'))):
            if d.get('actuation_enabled') is not False:
                raise RuntimeError('Unexpected actuator capability')
            seen.add(seq)
            rows.append(dict(at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
                seq=seq, vision=vision, tracking=tracking, model_backend=d.get('model_backend'),
                model_error=d.get('model_load_error'), source_age_ms=d.get('source_age_ms'),
                result_age_ms=d.get('result_age_ms'), detection_fps=d.get('detection_fps'),
                camera=d.get('camera_source')))
        if len(rows) >= 40 and time.monotonic()-started >= 3:
            break
        time.sleep(.025)
    if not rows:
        raise RuntimeError('No fresh live frames for mode '+mode)
    with urllib.request.urlopen(BASE + '/frame.jpg', timeout=6) as response:
        (folder / (mode+'-result.jpg')).write_bytes(response.read())
    (folder / (mode+'-samples.json')).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    errors = sorted(set(str(value) for r in rows for value in
        (r['model_error'], r['vision'].get('model_error'), r['vision'].get('face_error')) if value))
    counts = dict(objects=max(len(r['vision'].get('objects', [])) for r in rows),
                  faces=max(len(r['vision'].get('faces', [])) for r in rows),
                  tags=max(len(r['vision'].get('tags', [])) for r in rows),
                  colors=sorted(set(c['color'] for r in rows for c in r['vision'].get('colors', []))),
                  motion_frames=sum(bool(r['vision'].get('motion_event')) for r in rows))
    states = {state:sum(r['tracking'].get('state')==state for r in rows)
              for state in sorted(set(r['tracking'].get('state') for r in rows))}
    positive = any(r['tracking'].get('bbox') is not None for r in rows)
    return dict(fresh_frames=len(rows), states=states, candidates_observed=positive,
                counts=counts, errors=errors, inference_ms=stats([r['vision']['inference_ms'] for r in rows if r['vision'].get('inference_ms') is not None]),
                face_ms=stats([r['vision'].get('stage_ms', {}).get('face_ms', 0) for r in rows]) if mode=='face' else None,
                acceptance='LIVE_CANDIDATE_OBSERVED' if positive and not errors else
                           'LIVE_RAN_NO_POSITIVE_IN_SCENE' if not errors else 'ERROR',
                accuracy_validated=False, actuation_enabled=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modes',nargs='+',choices=('red','green','blue','person','face','tag'),default=('red','green','blue','person','face','tag'))
    parser.add_argument('--wait-tag',type=int)
    parser.add_argument('--wait-seconds',type=int,default=120)
    args=parser.parse_args()
    if not 1<=args.wait_seconds<=180:parser.error('wait-seconds must be 1..180')
    OUT.mkdir(parents=True, exist_ok=True)
    folder = OUT / ('live-'+datetime.datetime.now().strftime('%H%M%S'))
    folder.mkdir(exist_ok=False)
    before = get('/api/status')
    camera = before.get('camera_source') or {}
    if not camera.get('valid') or camera.get('usb_identity') != '145F:02EC':
        raise RuntimeError('Expected fresh selected original camera')
    if args.wait_tag is not None:
        print(json.dumps({'waiting_for_live_tag':args.wait_tag,'timeout_seconds':args.wait_seconds}),flush=True)
        deadline=time.monotonic()+args.wait_seconds
        while time.monotonic()<deadline:
            d=get('/api/status')
            if d.get('vision_valid') and any(t['id']==args.wait_tag for t in (d.get('vision') or {}).get('tags', [])):
                print(json.dumps({'live_tag_observed':args.wait_tag}),flush=True)
                break
            time.sleep(.2)
        else:
            result=dict(acceptance='TARGET_NOT_OBSERVED_BEFORE_TIMEOUT',tag=args.wait_tag,actuation_enabled=False)
            (folder/'target-wait.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(json.dumps(result));return
        before=get('/api/status')
    previous = before.get('tracking') or {}
    report = dict(camera=camera, started=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
                  live_modes={}, actuation_enabled=False, telemetry_connected=before.get('connected'),
                  physical_gimbal_test=False, physical_line_test=False, exposure_to_screen_latency_verified=False)
    try:
        for mode in args.modes:
            result = observe_mode(mode, folder)
            report['live_modes'][mode] = result
            print(json.dumps({'mode': mode, **result}, ensure_ascii=False), flush=True)
        config(previous.get('mode', 'red'), previous.get('enabled', True))
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = {endpoint:pool.submit(stream, endpoint, folder) for endpoint in ('preview.mjpeg', 'detection.mjpeg')}
            report['streams'] = {endpoint:job.result() for endpoint,job in jobs.items()}
        report['events'] = get('/api/events')
        report['final_status'] = get('/api/status')
    finally:
        config(previous.get('mode', 'red'), previous.get('enabled', True))
        (folder / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(folder/'report.json'), 'streams':
        {key:{k:v for k,v in value.items() if k!='samples'} for key,value in report.get('streams', {}).items()}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
