"""Call the real bridge/model. Default fixture is explicitly synthetic, not a camera.

--camera uses only a currently valid frame from the configured gateway. It never
starts capture, changes configuration, or controls the car.
"""
from pathlib import Path
import argparse
import base64
import datetime
import io
import json
import time
from urllib.request import Request, build_opener, ProxyHandler
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'output/onboard_dashboard/large-vision-20261107'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--camera', action='store_true')
    args = parser.parse_args()
    runtime = json.loads((OUT/'runtime.json').read_text(encoding='utf-8'))
    base = runtime['url'].rstrip('/')
    origin = 'http://127.0.0.1:'+str(runtime['port'])
    opener = build_opener(ProxyHandler({}))
    def get(path):
        return json.load(opener.open(base+'/api/'+path, timeout=6))
    if args.camera:
        camera = get('camera/status')
        if not camera.get('running') or not camera.get('valid') or camera.get('age_ms', 999999)>2000:
            raise RuntimeError('没有新鲜车载相机画面，本轮不作相机验收')
        raw = opener.open(base+'/api/camera/frame', timeout=4).read()
        source = 'camera_snapshot'
        seq = str(camera.get('seq', ''))
    else:
        pic = Image.new('RGB', (640, 480), 'white')
        draw = ImageDraw.Draw(pic)
        draw.rectangle((60, 140, 240, 330), fill=(200, 30, 25))
        draw.ellipse((390, 140, 570, 320), fill=(25, 65, 215))
        draw.text((10, 10), 'SYNTHETIC TEST - NOT CAMERA', fill='black')
        encoded = io.BytesIO()
        pic.save(encoded, format='JPEG')
        raw, source, seq = encoded.getvalue(), 'synthetic_test', ''
    captured = datetime.datetime.now(datetime.timezone.utc).isoformat()
    body = dict(image_base64=base64.b64encode(raw).decode(), question='请描述这张图中的主要物体、颜色及左右位置。', input_source=source,
                captured_at=captured, frame_seq=seq)
    response = opener.open(Request(base+'/api/vlm/analyze', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json', 'Origin': origin}), timeout=8)
    job = json.load(response)
    print(json.dumps({'submitted': True, 'id': job['id'], 'source': source}), flush=True)
    until = time.monotonic()+175
    while time.monotonic()<until:
        job = get('vlm/job/'+job['id'])
        if job['state'] != 'running':
            report = {**job, 'physical_camera_used': args.camera, 'recognition_accuracy_validated': False}
            (OUT/('camera-model-result.json' if args.camera else 'synthetic-model-result.json')).write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=False), flush=True)
            if job['state'] != 'done':
                raise SystemExit(1)
            return
        time.sleep(.8)
    raise RuntimeError('超过本次等待时限')


if __name__ == '__main__':
    main()
