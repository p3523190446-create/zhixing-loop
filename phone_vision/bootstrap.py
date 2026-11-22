"""Fetch pinned, checksum-verified native build inputs; no global SDK install."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import subprocess
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
CACHE = Path.home() / '.cache' / 'zhixing-android-tools'
TAG = '20260527.f1ac75e'


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'zhixing-vision-build'})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read()


def install(item):
    name, url, size, algorithm, expected = item
    archive = CACHE / name
    target = CACHE / name.removesuffix('.zip')
    marker = target / '.verified-extraction.json'
    if marker.exists() and json.loads(marker.read_text(encoding='utf-8'))['digest'] == expected:
        print('Ready:', name, flush=True)
        return str(target)
    if not archive.exists() or archive.stat().st_size != size:
        print('Downloading:', name, flush=True)
        subprocess.run(['curl.exe', '-L', '--fail', '--silent', '--show-error',
                        '--connect-timeout', '20', '--max-time', '420', url,
                        '-o', str(archive)], check=True)
    digest = hashlib.file_digest(archive.open('rb'), algorithm).hexdigest()
    if archive.stat().st_size != size or digest != expected:
        raise RuntimeError('Checksum mismatch: ' + name)
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as contents:
        for member in contents.namelist():
            if not (target / member).resolve().is_relative_to(target.resolve()):
                raise RuntimeError('Unsafe archive member')
        contents.extractall(target)
    marker.write_text(json.dumps({'digest': digest, 'source': url}), encoding='utf-8')
    print('Verified and extracted:', name, flush=True)
    return str(target)


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    # Pinned to metadata verified on 2026-10-07. Rebuilds do not silently upgrade tools.
    google = 'https://dl.google.com/android/repository/'
    inputs = [
        ('android-ndk-r29-windows.zip', google + 'android-ndk-r29-windows.zip', 833850862, 'sha1', 'ab3bb30fbb9e6903666d60c55d11e78b04e07472'),
        ('build-tools_r35_windows.zip', google + 'build-tools_r35_windows.zip', 59878107, 'sha1', 'af059bb67cf7786f45ee0db85e2d24985df1b4b6'),
        ('cmake-3.31.5-windows.zip', google + 'cmake-3.31.5-windows.zip', 20465729, 'sha1', '6a51cf2d1f300edecbf04603087a31b07a0fcdec'),
        ('platform-33-ext3_r03.zip', google + 'platform-33-ext3_r03.zip', 67334237, 'sha1', '394bc86d8d3452aa4d419b67743025a6fb2cd9d0'),
        ('ncnn-20260526-android-vulkan.zip', 'https://github.com/Tencent/ncnn/releases/download/20260526/ncnn-20260526-android-vulkan.zip', 32950551, 'sha256', '26909c92eed35afed4a966b5e9e503fcb0a529691ea3f910ec2c94a4fff52804'),
        ('opencv-mobile-4.13.0-android.zip', 'https://github.com/nihui/opencv-mobile/releases/download/v36/opencv-mobile-4.13.0-android.zip', 19789373, 'sha256', '56735469e0c344253122cbc66f5e69e5f3b2c131a0f892eb68fa5530be763b83'),
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(install, inputs))
    manifest = {'upstream_tag': TAG, 'cache': str(CACHE),
                'inputs': [dict(name=i[0], url=i[1], digest=i[4], extracted=p)
                           for i, p in zip(inputs, paths)]}
    (HERE / 'build-inputs.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Build inputs ready.', flush=True)


if __name__ == '__main__':
    main()
