"""Install only the VLM UI update; preserve all existing phone settings."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import socket
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT/'知行回路软件/debug_ui'
OUT = ROOT/'output/onboard_dashboard/large-vision-20261107'
ADB = ROOT/'tmp/android-tools/platform-tools/adb.exe'


def adb(*a):
    return subprocess.run([str(ADB), *a], capture_output=True, check=True, timeout=20).stdout


def preferences():
    return {name: hashlib.sha256(adb('shell', 'run-as', 'cn.zhixing.dashboard', 'cat',
                                    'shared_prefs/'+name+'.xml')).hexdigest()
            for name in ('web', 'gimbal_profile', 'line_calibration')}


def main():
    # Existing installer also checks unique device, platform, version, signature,
    # current APK backup, install -r (never clears data), and exact readback hash.
    before = preferences()
    (OUT/'settings-before.json').write_text(json.dumps(before), encoding='utf-8')
    subprocess.run([sys.executable, str(UI/'install_camera_compat.py'), '--out', str(OUT)], check=True)
    after = preferences()
    if after != before:
        raise RuntimeError('已有参数发生变化，请检查，不继续自动运行')
    (OUT/'settings-preserved.json').write_text(json.dumps({'preserved': True, 'before': before, 'after': after}), encoding='utf-8')
    adb('shell', 'am', 'start', '-n', 'cn.zhixing.dashboard/.MainActivity')
    build = json.loads((OUT/'build-result.json').read_text(encoding='utf-8'))
    configured = False
    if build['version_code'] >= 31 and (OUT/'lan-source-private.json').is_file():
        phone_lan = json.loads((OUT/'lan-source-private.json').read_text(encoding='utf-8'))['url']
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((urlsplit(phone_lan).hostname, 8780))
            computer_ip = sock.getsockname()[0]
        bridge = json.loads((OUT/'runtime.json').read_text(encoding='utf-8'))
        model_url = 'http://'+computer_ip+':'+str(bridge['port'])+bridge['base']
        opener = build_opener(ProxyHandler({}))
        for _ in range(30):
            try:
                phone = json.loads(adb('shell', 'run-as', 'cn.zhixing.dashboard', 'cat', 'files/web-runtime.json'))
                adb('forward', 'tcp:18781', 'tcp:'+str(phone.get('port', 8780)))
                url = 'http://127.0.0.1:18781'+phone['base']
                info = json.load(opener.open(url+'/api/ui/info', timeout=2))
                if info.get('source_version') != build['version']:
                    raise ValueError('等待新版服务')
                body = json.dumps({'url': model_url}).encode('utf-8')
                result = json.load(opener.open(Request(url+'/api/vlm/settings', data=body,
                    headers={'Origin': 'http://127.0.0.1:18781', 'Content-Type': 'application/json'}), timeout=2))
                configured = result.get('url') == model_url
                if not configured:
                    raise ValueError('模型地址未核对通过')
                (OUT/'shared-model-config-private.json').write_text(json.dumps(result), encoding='utf-8')
                break
            except (OSError, ValueError, subprocess.SubprocessError):
                time.sleep(.15)
        if not configured:
            raise RuntimeError('修补版已安装，但共享模型地址未配置成功，请检查手机服务')
    print(json.dumps({'installed': True, 'settings_preserved': list(before), 'version': build['version'],
                      'shared_model_address_configured': configured,
                      'firmware_changed': False, 'nonzero_actuator_commands': 0}))


if __name__ == '__main__':
    main()
