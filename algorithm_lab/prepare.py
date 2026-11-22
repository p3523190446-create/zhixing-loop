"""Fetch the official Apache-2.0 OpenCV Zoo detector at one pinned revision.

The LFS pointer is the authority for the ONNX size and SHA256. No downloaded
Python code is executed by this preparation step.
"""
from pathlib import Path
import hashlib, json, re, urllib.request

HERE = Path(__file__).resolve().parent
DEST = HERE / 'vendor/opencv_zoo_yolox'

def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Zhixing-algorithm-lab/1'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()

def main():
    DEST.mkdir(parents=True, exist_ok=True)
    lock = DEST / 'provenance.json'
    if lock.exists():
        old = json.loads(lock.read_text(encoding='utf-8'))
        model = DEST / old['model']
        if model.exists() and hashlib.sha256(model.read_bytes()).hexdigest() == old['sha256']:
            print(json.dumps({'status': 'verified_cached', 'commit': old['commit']})); return
    sha = json.loads(fetch('https://api.github.com/repos/opencv/opencv_zoo/commits/main'))['sha']
    if not re.fullmatch('[0-9a-f]{40}', sha):
        raise ValueError('Unexpected Git revision')
    folder = 'models/object_detection_yolox/'
    raw = f'https://raw.githubusercontent.com/opencv/opencv_zoo/{sha}/' + folder
    files = {}
    for name in ['yolox.py', 'LICENSE', 'README.md', 'demo.py']:
        data = fetch(raw + name)
        (DEST / name).write_bytes(data)
        files[name] = hashlib.sha256(data).hexdigest()
    name = 'object_detection_yolox_2022nov.onnx'
    pointer = fetch(raw + name).decode('ascii')
    digest = re.search(r'oid sha256:([a-f0-9]{64})', pointer).group(1)
    size = int(re.search(r'^size (\d+)$', pointer, re.M).group(1))
    model_url = f'https://media.githubusercontent.com/media/opencv/opencv_zoo/{sha}/' + folder + name
    data = fetch(model_url)
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Official model LFS verification failed; model not installed')
    (DEST / name).write_bytes(data)
    info = dict(repository='https://github.com/opencv/opencv_zoo', commit=sha,
                license='Apache-2.0', model=name, size=size, sha256=digest,
                source_files=files, model_url=model_url, source_modified=False)
    lock.write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(info))

if __name__ == '__main__':
    main()
