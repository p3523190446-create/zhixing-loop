"""Saved real-frame CPU/CUDA benchmark and explicitly controlled image checks."""
import bootstrap
import datetime
import json
from pathlib import Path
import statistics
import time
import cv2 as cv
import numpy as np
from core import Vision, LineFollower, WHITE, BLACK
from tracking import TargetTracker
from odometry import Odometry
from ort_detector import OrtYoloX

HERE = Path(__file__).resolve().parent
OUT = bootstrap.ROOT/'output/onboard_dashboard/algorithm-experiments-20261026'


def summary(values):
    ordered = sorted(values)
    return dict(median_ms=statistics.median(ordered), p95_ms=ordered[min(len(ordered)-1, int(len(ordered)*.95))], samples_ms=values)


def main():
    folder = OUT/('controlled-'+datetime.datetime.now().strftime('%H%M%S'))
    folder.mkdir(parents=True, exist_ok=False)
    target = cv.imdecode(np.frombuffer((OUT/'camera-test-target.png').read_bytes(), np.uint8), cv.IMREAD_COLOR)
    vision = Vision()
    targets, drawn = vision.process(target, 1)
    ok, data = cv.imencode('.jpg', drawn)
    if not ok:
        raise RuntimeError('Failed to encode controlled observation')
    (folder/'generated-target-result.jpg').write_bytes(data.tobytes())
    assert sorted(c['color'] for c in targets['colors']) == ['blue', 'green', 'red']
    assert [tag['id'] for tag in targets['tags']] == [7]
    controlled = {}
    blank = dict(colors=[], tags=[], objects=[], faces=[])
    for mode in ('red', 'green', 'blue', 'tag'):
        tracker = TargetTracker()
        tracker.configure(dict(mode=mode, enabled=True))
        sequence = [tracker.update(targets, target.shape[1], target.shape[0], 20) for _ in range(4)]
        assert sequence[-1]['state'] == 'TRACKING'
        lost = tracker.update(blank, target.shape[1], target.shape[0], 20)
        assert lost['pointing_request'] is None
        stale = tracker.update(targets, target.shape[1], target.shape[0], 250)
        assert stale['state'] == 'STALE' and stale['pointing_request'] is None
        tracker.configure(dict(enabled=False))
        paused = tracker.update(targets, target.shape[1], target.shape[0], 20)
        assert paused['state'] == 'PAUSED'
        controlled[mode] = dict(lock_states=[d['state'] for d in sequence], lost=lost, stale=stale, paused=paused)
    changed, _ = vision.process(np.zeros_like(target), 1.2)
    assert changed['motion_event']
    lines = {}
    for mask, expected in ((255, 'no_line'), (0, 'all_black'), (250, 'junction'), (231, 'line'), (254, 'line'), (127, 'line')):
        raw = [BLACK[i] if not mask & (1 << i) else WHITE[i] for i in range(8)]
        state = dict(connected=True, line=dict(valid=True, raw=raw, digital_mask=mask, age_ms=10, analog_frames=1))
        result = LineFollower().update(state)
        assert result['state'] == expected and result['actuation_enabled'] is False
        lines[str(mask)] = result
    odometry = Odometry(200, 1, [1, 1, 1, 1])
    odometry.update([100]*4, 1, True, 1000)
    distance = odometry.update([100]*4, 1.1, True, 1100)
    assert abs(distance['x_mm']-10) < 1e-6
    gap = odometry.update([100]*4, 3, True, 3000)
    assert gap['valid'] is False
    report = dict(mode='CONTROLLED_GENERATED_TARGETS_AND_SENSOR_INPUTS',
        physical_line_or_odometry_verified=False, live_camera_accuracy_validated=False,
        colors=targets['colors'], tags=targets['tags'], tracking=controlled,
        scene_change=changed['motion_fraction'], line_cases=lines,
        odometry_example=distance, odometry_gap=gap, actuation_enabled=False)
    (folder/'controlled-inputs.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'controlled_cases': 'PASS', 'report': str(folder/'controlled-inputs.json')}, ensure_ascii=False), flush=True)

    live = sorted(OUT.glob('live-*/preview-first.jpg'))[-1]
    image = cv.imdecode(np.frombuffer(live.read_bytes(), np.uint8), cv.IMREAD_COLOR)
    h, w = image.shape[:2]
    ratio = min(640/h, 640/w)
    padded = np.full((640, 640, 3), 114, np.float32)
    resized = cv.resize(image, (int(w*ratio), int(h*ratio))).astype(np.float32)
    padded[:resized.shape[0], :resized.shape[1]] = resized
    model_dir = HERE/'vendor/opencv_zoo_yolox'
    cpu = Vision(model_dir, backend='cpu')
    if cpu.model is None:
        raise RuntimeError(cpu.model_error)
    gpu = OrtYoloX(model_dir, profile=True)
    results, detections = {}, {}
    for name, model in (('cpu', cpu.model), ('cuda', gpu)):
        for _ in range(3):
            model.infer(padded.copy())
        timings = []
        for _ in range(12):
            started = time.perf_counter()
            boxes = model.infer(padded.copy())
            timings.append((time.perf_counter()-started)*1000)
        results[name] = dict(**summary(timings), count=len(boxes))
        detections[name] = boxes.tolist()
    unmatched = list(detections['cuda'])
    for a in detections['cpu']:
        match = next((index for index, b in enumerate(unmatched)
            if int(a[-1]) == int(b[-1]) and abs(a[-2]-b[-2]) < .02
            and max(abs(x-y) for x,y in zip(a[:4], b[:4])) < 2), None)
        if match is None:
            raise AssertionError('No CUDA match for CPU result within saved tolerance')
        unmatched.pop(match)
    if unmatched:
        raise AssertionError('CUDA produced extra results beyond parity tolerance')
    profile_path = Path(gpu.session.end_profiling())
    profile = json.loads(profile_path.read_text(encoding='utf-8'))
    (folder/'ort-profile.json').write_bytes(profile_path.read_bytes())
    providers = {}
    for event in profile:
        provider = event.get('args', {}).get('provider')
        if provider:
            providers[provider] = providers.get(provider, 0)+1
    assert providers.get('CUDAExecutionProvider', 0) > 0
    benchmark = dict(mode='REPLAY_OF_A_REAL_CAMERA_FRAME', source=str(live), same_model=True,
        parity_pass=True, tolerance=dict(score=.02, bbox_input_pixels=2),
        detections=detections, results=results, executed_providers=providers,
        actual_cuda_execution_verified=True, live_viewer_running_during_benchmark=True,
        accuracy_ground_truth_available=False, exposure_to_screen_latency_verified=False)
    (folder/'real-frame-benchmark.json').write_text(json.dumps(benchmark, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'benchmark_report': str(folder/'real-frame-benchmark.json'), 'results':results, 'executed_providers':providers}, ensure_ascii=False))


if __name__ == '__main__':
    main()
