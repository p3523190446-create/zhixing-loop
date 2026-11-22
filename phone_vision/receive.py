"""Receive actual phone detections over USB ADB; never synthesize detections."""
from pathlib import Path
import argparse
import datetime
import json
import math
import os
import queue
import subprocess
import threading
import time

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
DEFAULT_ADB = WORKSPACE / 'tmp/android-tools/platform-tools/adb.exe'
OUTPUT = WORKSPACE / 'output/phone_vision'
NAMES = json.loads((HERE / 'coco-labels.json').read_text(encoding='utf-8'))
CHINESE = {0: '人', 2: '汽车', 15: '猫', 16: '狗', 39: '瓶子', 41: '杯子',
           45: '碗', 56: '椅子', 60: '餐桌', 63: '笔记本电脑', 67: '手机'}


def validate(frame):
    if frame.get('v') != 1 or frame.get('task') != 'coco':
        raise ValueError('Unsupported protocol')
    for field in ('seq', 'phone_ms', 'width', 'height'):
        if type(frame.get(field)) is not int or frame[field] <= 0:
            raise ValueError('Invalid ' + field)
    timing = frame.get('infer_ms')
    if not isinstance(timing, (int, float)) or not math.isfinite(timing) or timing < 0:
        raise ValueError('Invalid inference timing')
    objects = frame.get('objects')
    if not isinstance(objects, list) or len(objects) > 8:
        raise ValueError('Invalid object list')
    for item in objects:
        if not isinstance(item, dict):
            raise ValueError('Invalid object record')
        if type(item.get('cls')) is not int or not 0 <= item['cls'] < 80:
            raise ValueError('Invalid class')
        for field in ('score', 'cx', 'cy', 'w', 'h'):
            value = item.get(field)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError('Invalid normalized value')
        item['name'] = NAMES[item['cls']]
        item['label_cn'] = CHINESE.get(item['cls'], item['name'])
        item['position'] = '左侧' if item['cx'] < .4 else '右侧' if item['cx'] > .6 else '中央'
    return frame


def command(adb, *args):
    result = subprocess.run([str(adb), *args], capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=15)
    if result.returncode:
        raise RuntimeError('ADB command failed')
    return result.stdout.strip()


def save_latest(frame):
    temporary = OUTPUT / 'latest_detection.tmp'
    temporary.write_text(json.dumps(frame, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, OUTPUT / 'latest_detection.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', type=Path, default=DEFAULT_ADB)
    parser.add_argument('--duration', type=float, default=30)
    options = parser.parse_args()
    entries = [line.split() for line in command(options.adb, 'devices').splitlines()[1:] if line.strip()]
    if len(entries) != 1 or entries[0][1] != 'device':
        raise RuntimeError('Exactly one authorized phone is required')
    device = entries[0][0]  # Used only for routing, never printed or persisted.
    pid = command(options.adb, '-s', device, 'shell', 'pidof', 'cn.zhixing.vision')
    if not pid:
        raise RuntimeError('Open the Zhixing vision app first')
    process = subprocess.Popen([str(options.adb), '-s', device, 'logcat', '--pid=' + pid.split()[0],
                                '-v', 'raw', '-T', '1', 'ZXR_VISION:I', '*:S'],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               text=True, encoding='utf-8', errors='replace')
    messages = queue.Queue()
    def reader():
        for line in process.stdout:
            messages.put(line)
        messages.put(None)
    threading.Thread(target=reader, daemon=True).start()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    evidence = OUTPUT / ('phone-detections-' + stamp + '.jsonl')
    frames, objects, invalid = 0, 0, 0
    first = last = last_print = None
    previous_sequence = 0
    latest = None
    print('等待手机的真实检测数据；无目标时也会发送空列表。', flush=True)
    try:
        with evidence.open('w', encoding='utf-8') as log:
            while time.monotonic() - start < options.duration:
                try:
                    line = messages.get(timeout=.5)
                except queue.Empty:
                    continue
                if line is None:
                    break
                if not line.lstrip().startswith('{'):
                    continue
                try:
                    frame = validate(json.loads(line))
                except (ValueError, TypeError, KeyError):
                    invalid += 1
                    continue
                if frame['seq'] <= previous_sequence:
                    continue
                previous_sequence = frame['seq']
                now = time.monotonic()
                first = now if first is None else first
                last = now
                frames += 1; objects += len(frame['objects'])
                frame['pc_received_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                frame['receive_status'] = 'live'
                log.write(json.dumps(frame, ensure_ascii=False) + '\n'); log.flush()
                save_latest(frame); latest = frame
                if last_print is None or now - last_print >= .5:
                    details = '；'.join(f"{o['label_cn']} {o['score']:.0%} {o['position']}"
                                       for o in frame['objects']) or '无有效目标'
                    print(f"帧 {frame['seq']} | {details} | 识别耗时 {frame['infer_ms']:.0f}ms", flush=True)
                    last_print = now
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait()
        if latest:
            latest['receive_status'] = 'monitor_stopped'
            save_latest(latest)
    rate = (frames - 1) / (last - first) if frames > 1 and last > first else None
    summary = {'source': 'live phone native detections over USB ADB', 'frames': frames,
               'object_observations': objects, 'invalid_messages': invalid,
               'received_frames_per_second': rate, 'evidence': str(evidence),
               'phone_to_motor_latency_measured': False,
               'car_control_connected': False}
    (OUTPUT / 'receive-verification.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=True), flush=True)
    return 0 if frames else 2


if __name__ == '__main__':
    raise SystemExit(main())
