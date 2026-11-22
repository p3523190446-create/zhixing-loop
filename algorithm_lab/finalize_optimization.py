"""Record final live state and preserve concurrent project/UI updates."""
import bootstrap
from pathlib import Path
import hashlib,json,time,urllib.request
from server import OUT,HERE,timestamp

def main():
    dest=bootstrap.ROOT/'output/onboard_dashboard/algorithm-optimization-20261025'
    samples=[]
    for _ in range(12):
        with urllib.request.urlopen('http://127.0.0.1:8796/api/status',timeout=4) as response:d=json.load(response)
        assert d['model_backend']=='onnxruntime_cuda' and d['vision_valid']
        assert d['actuation_enabled'] is False and d['telemetry']['speed_targets']==[0]*4
        assert not d['telemetry']['drive']['active'] and not d['telemetry']['gimbal']['active']
        samples.append(d);time.sleep(.1)
    with urllib.request.urlopen('http://127.0.0.1:8796/api/events') as response:events=json.load(response)
    performance=json.loads((dest/'live-pipeline-performance.json').read_text(encoding='utf-8'))
    benchmark=json.loads((dest/'detector-benchmark.json').read_text(encoding='utf-8'))
    runtime=json.loads((OUT/'runtime.json').read_text(encoding='utf-8'))
    result=dict(at=timestamp(),status='LIVE_GPU_DESKTOP_TRACKING_EVENTS',url=runtime['url'],pid=runtime['pid'],
        backend='onnxruntime_cuda',capture_resolution='960x768',
        preview_fps=performance['results']['preview.mjpeg']['fps'],
        detection_fps=performance['results']['detection.mjpeg']['fps'],
        model_median_ms=benchmark['results']['cuda']['median_ms'],
        host_result_age_median_ms=performance['results']['detection.mjpeg']['host_age_median_ms'],
        latency_scope=performance['source_age_definition'],exposure_to_screen_verified=False,
        software_tests=10,browser_checks=21,live_samples=samples,events=events,
        gimbal_actuation_enabled=False,camera_mounted_on_gimbal=False,
        gimbal_block='User confirmed current camera on desk; mounting/axis mapping and prior gimbal power-dropout acceptance pending',
        firmware_changed=False,phone_apk_changed=False,nonzero_motion_commands=False,
        previous_sensor_ui_preserved=True,
        source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir() if p.suffix in ('.py','.js','.html')})
    (dest/'deployment-status.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    heading=('> **2026-10-25 GPU与跟踪最新：** [算法页](http://127.0.0.1:8796/)已用RTX5060/ORT CUDA；'
        '960×768预览短测约30fps，识别约22fps，同模型推理由CPU约271ms降到GPU约12ms。'
        '颜色/人物/人脸/路标跟踪计算、丢失撤请求和事件照片已运行。用户确认借用镜头仍在桌面，'
        '云台实物执行未开启，安装/轴向与旧供电掉线待验。原8795感知界面及他人更新保留。'
        '详见机器人比赛计划/知行回路软件/algorithm_lab/优化与跟踪-2026-10-25.md；'
        '证据output/onboard_dashboard/algorithm-optimization-20261025/deployment-status.json。\n\n')
    for path in [bootstrap.ROOT/'先看这页.md',bootstrap.ROOT.parent/'新生嵌入式比赛 2/先看这页.md']:
        old=path.read_bytes();text=old.decode('utf-8-sig')
        if '**2026-10-25 GPU与跟踪最新：**' not in text:
            if path.read_bytes()!=old:raise RuntimeError('Entry page changed concurrently')
            path.write_text(heading+text,encoding='utf-8')
    readme=HERE/'README.md';text=readme.read_text(encoding='utf-8')
    if '## GPU与跟踪最新' not in text:
        text=text.replace('# 知行回路算法调试','# 知行回路算法调试\n\n## GPU与跟踪最新\n\n第二轮已启用CUDA与约30fps预览/22fps识别流，增加连续目标跟踪、按需人脸分支与事件照片；[实际范围和验证](优化与跟踪-2026-10-25.md)。以下首轮说明保留作历史，15fps/CPU等旧状态由第二轮覆盖。',1)
        readme.write_text(text,encoding='utf-8')
    path=bootstrap.ROOT/'比赛备案/项目状态.json';raw=path.read_bytes();data=json.loads(raw.decode('utf-8-sig'))
    backup=dest/'project-status-before-optimization.json'
    if not backup.exists():backup.write_bytes(raw)
    data['algorithm_optimization_20261025']={k:v for k,v in result.items() if k not in ('live_samples','events','source_sha256')}
    if path.read_bytes()!=raw:raise RuntimeError('Project status changed concurrently; no overwrite')
    temp=path.with_name('项目状态.optimization.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(path)
    print(json.dumps({'status':result['status'],'samples':len(samples),'events':len(events),
                     'line_overflows_observed':samples[-1]['telemetry']['line']['overflows']}))

if __name__=='__main__':main()
