"""Save this round's actual read-only observations and update project entry points."""
import bootstrap
from pathlib import Path
import datetime,hashlib,json,time,urllib.request
from server import OUT,HERE,timestamp

def get():
    with urllib.request.urlopen('http://127.0.0.1:8796/api/status',timeout=4) as response:return json.load(response)

def main():
    samples=[]
    for _ in range(8):
        d=get();t=d.get('telemetry') or {}
        assert d.get('connected') and t.get('demo') is False
        assert d.get('actuation_enabled') is False
        assert not (t.get('drive') or {}).get('active')
        assert not (t.get('gimbal') or {}).get('active')
        assert t.get('speed_targets')==[0,0,0,0]
        assert d.get('model_ready') and not d.get('model_load_error')
        samples.append(d);time.sleep(.3)
    assert len({x['telemetry']['line']['analog_frames'] for x in samples})>=2
    (OUT/'borrowed-camera-real-checks.json').write_text(json.dumps(dict(
        at=timestamp(),mode='REAL_P9_READONLY',samples=samples,
        camera_live_verified=any(d.get('vision_valid') for d in samples),
        actuation_enabled=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    runtime=json.loads((OUT/'runtime.json').read_text(encoding='utf-8'))
    offline=json.loads((OUT/'offline-verification.json').read_text(encoding='utf-8'))
    performance=json.loads((OUT/'preview-performance.json').read_text(encoding='utf-8'))
    status=dict(at=timestamp(),status='FIRST_SOFTWARE_BATCH_LIVE_SHADOW',
        url=runtime['url'],service_pid=runtime['pid'],real_board_samples=len(samples),
        live_line=True,live_camera=any(d.get('vision_valid') for d in samples),
        model_loaded=True,model='OpenCV Zoo YOLOX-s CPU',offline_only_images=len(offline['results']),
        software_tests_passed=6,browser_checks_passed=13,
        preview_resolution='960x768',native_camera_mode='1920x1536 UYVY nominal 30fps',
        preview_received_fps=performance['received_fps'],detection_fps=performance['detection_fps'],
        preview_and_detection_decoupled=True,
        browser_evidence='新生嵌入式比赛 2/outputs/check-algorithm-page.cjs and output/playwright/algorithms-live.png',
        camera_block=None,
        camera_scope='User selected borrowed USB031 04B4:00C3; current PC real capture and model output verified. '
                     'The older camera and Hub data route remain unverified in this round.',
        mpu='Invalid after MCU reboot; nonstandard 0x72 compatibility trial was not re-enabled',
        motion_commands_sent=False,firmware_changed=False,phone_apk_changed=False,
        missing=['physical gimbal stability','physical independent stop',
                 'steering orientation and dynamic calibration','measured odometry calibration',
                 'verified driving labels and learned model','map perception and localization'],
        sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')})
    path=OUT/'deployment-status.json'
    old_status=OUT/'first-batch-camera-pending.json'
    if path.exists() and not old_status.exists():old_status.write_bytes(path.read_bytes())
    path.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    top=('> **2026-10-25算法调试首轮：** [打开算法页](http://127.0.0.1:8796/)；'
         '已接当前P9八路数据，提供位置/PD纠偏建议；YOLOX、红绿蓝色块、AprilTag及画面变化算法已接入计算模块。'
         '已改用借用USB031相机，真实采集及模型输出已通；按用户反馈降为960×768，预览与识别分开。'
         f'本次本机HTTP接收46帧/约3秒，预览{performance["received_fps"]:.1f}fps、识别约{performance["detection_fps"]}fps；这是短测，非耐久/端到端执行时延验收。'
         'MPU当前非标准身份默认拒绝采样；无刷写、无非零运动、手机仍0.21未更新。'
         '细节：机器人比赛计划/知行回路软件/algorithm_lab/README.md；证据output/onboard_dashboard/algorithms-20261025/deployment-status.json。\n\n')
    for path in [bootstrap.ROOT/'先看这页.md',bootstrap.ROOT.parent/'新生嵌入式比赛 2/先看这页.md']:
        old=path.read_text(encoding='utf-8')
        if '**2026-10-25算法调试首轮：**' in old:
            start=old.index('> **2026-10-25算法调试首轮：**');end=old.index('\n\n',start)+2
            path.write_text(old[:start]+top+old[end:],encoding='utf-8')
        else:path.write_text(top+old,encoding='utf-8')
    path=bootstrap.ROOT/'比赛备案/项目状态.json'
    raw=path.read_bytes();d=json.loads(raw.decode('utf-8-sig'))
    backup=OUT/'project-status-before.json'
    if not backup.exists():backup.write_bytes(raw)
    d['software_algorithms_20261025']=status
    if path.read_bytes()!=raw:raise RuntimeError('Project status changed concurrently; update not written')
    temp=path.with_name('项目状态.algorithms.tmp')
    temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(path)
    print(json.dumps({'real_samples':len(samples),'live_camera':status['live_camera'],'status':status['status']}))

if __name__=='__main__':main()
