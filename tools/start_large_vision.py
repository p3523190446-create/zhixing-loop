"""Start the existing local VLM bridge; optionally reuse connected phone camera.

No robot serial ports or actuator commands. USB forwarding is for development;
LAN use can pass --source-url with the phone's actual web address.
"""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import time
from urllib.request import build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT/'知行回路软件/debug_ui'
OUT = ROOT/'output/onboard_dashboard/large-vision-20261107'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-url')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    runtime = OUT/'runtime.json'
    opener = build_opener(ProxyHandler({}))
    try:
        old = json.loads(runtime.read_text(encoding='utf-8'))
        health = json.load(opener.open(old['url'].rstrip('/')+'/api/vlm/status', timeout=2))
        if health.get('model') == 'qwen3-vl:8b-instruct':
            print(json.dumps({'reused': True, **old}, ensure_ascii=False))
            return
    except (OSError, ValueError, KeyError):
        pass
    source = args.source_url
    if not source:
        try:
            last = json.loads((OUT/'lan-source-private.json').read_text(encoding='utf-8'))['url']
            opener.open(last.rstrip('/')+'/api/ui/info', timeout=2).close()
            source = last
        except (OSError, ValueError, KeyError):
            pass
    if not source:
        adb = ROOT/'tmp/android-tools/platform-tools/adb.exe'
        try:
            result = subprocess.run([str(adb), 'devices'], capture_output=True, timeout=8, check=True)
            devices = [r.split()[0] for r in result.stdout.decode().splitlines()[1:] if r.endswith('\tdevice')]
            if len(devices) == 1:
                def run(*a):
                    return subprocess.run([str(adb), '-s', devices[0], *a], capture_output=True, check=True, timeout=10).stdout
                phone = json.loads(run('shell', 'run-as', 'cn.zhixing.dashboard', 'cat', 'files/web-runtime.json'))
                port = phone.get('port', 8780)
                run('forward', 'tcp:18781', 'tcp:'+str(port))
                source = 'http://127.0.0.1:18781'+phone['base']
        except (OSError, ValueError, subprocess.SubprocessError):
            source = None
    command = [sys.executable, str(UI/'vision_large/server.py'), '--bind', '0.0.0.0', '--output', str(OUT)]
    if source:
        command += ['--source-url', source]
    # Never put the source's pairing path in the source tree or submission.
    (OUT/'source-private.json').write_text(json.dumps({'url': source}), encoding='utf-8')
    with (OUT/'service-stdout.log').open('ab') as out, (OUT/'service-stderr.log').open('ab') as err:
        proc = subprocess.Popen(command, cwd=str(UI), stdout=out, stderr=err,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    for _ in range(60):
        if proc.poll() is not None:
            raise RuntimeError('看图服务启动失败，请检查service-stderr.log')
        try:
            current = json.loads(runtime.read_text(encoding='utf-8'))
            if current['pid'] == proc.pid:
                opener.open(current['url'].rstrip('/')+'/api/vlm/status', timeout=2).close()
                print(json.dumps(current, ensure_ascii=False))
                return
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(.15)
    raise RuntimeError('看图服务启动尚未确认，请检查日志，不要重复启动')


if __name__ == '__main__':
    main()
