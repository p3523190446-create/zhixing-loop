"""Run this bounded algorithm-only executable on the connected phone over ADB."""
import bootstrap
from pathlib import Path
import hashlib,json,subprocess,time

ROOT=bootstrap.ROOT
OUT=ROOT/'output/onboard_dashboard/phone-first-20261025'
ADB=ROOT/'tmp/android-tools/platform-tools/adb.exe'
REMOTE='/data/local/tmp/zhixing_phone_bench_20261025'

def run(args,timeout=30):
    return subprocess.run([str(ADB),*args],check=True,capture_output=True,timeout=timeout)

def main():
    features=run(['shell','pm','list','features']).stdout.decode('utf-8',errors='replace')
    before=run(['shell','dumpsys','battery']).stdout.decode('utf-8',errors='replace')
    run(['shell','mkdir','-p',REMOTE])
    for name in ['zx_local_bench','yolov8n.ncnn.param','yolov8n.ncnn.bin','frame.rgb']:
        run(['push',str(OUT/name),REMOTE+'/'+name],timeout=40)
    run(['shell','chmod','700',REMOTE+'/zx_local_bench'])
    started=time.monotonic()
    proc=run(['shell',REMOTE+'/zx_local_bench',REMOTE],timeout=180)
    (OUT/'phone-stdout.json').write_bytes(proc.stdout)
    (OUT/'phone-stderr.log').write_bytes(proc.stderr)
    result=json.loads(proc.stdout.decode('utf-8'))
    assert result['mode']=='ANDROID_OFFLINE_ALGORITHM_ONLY' and not result['actuator_access']
    assert len(result['models'])==6 and all(0<x['median_ms']<10000 for x in result['models'])
    after=run(['shell','dumpsys','battery']).stdout.decode('utf-8',errors='replace')
    report=dict(scope='Actual phone executes offline archived RGB and pinned YOLOv8n; excludes UVC, live display and controller',
        phone=dict(platform=run(['shell','getprop','ro.board.platform']).stdout.decode().strip(),
                   sdk=run(['shell','getprop','ro.build.version.sdk']).stdout.decode().strip(),
                   features=features),result=result,elapsed_s=time.monotonic()-started,
        pc_inference=False,phone_backend='ncnn_cpu',vulkan_tested=False,
        battery_before=before,battery_after=after,device_files=REMOTE,
        executable_sha256=hashlib.sha256((OUT/'zx_local_bench').read_bytes()).hexdigest())
    (OUT/'phone-benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
