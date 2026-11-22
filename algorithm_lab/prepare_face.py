"""Install the small official MIT-licensed YuNet face detector, pinned and hashed."""
from pathlib import Path
import hashlib,json,re
from prepare import fetch,HERE

def main():
    pin=json.loads((HERE/'vendor/opencv_zoo_yolox/provenance.json').read_text(encoding='utf-8'))['commit']
    dest=HERE/'vendor/opencv_zoo_yunet';dest.mkdir(parents=True,exist_ok=True)
    folder='models/face_detection_yunet/'
    base=f'https://raw.githubusercontent.com/opencv/opencv_zoo/{pin}/'+folder
    for name in ['LICENSE','README.md']:(dest/name).write_bytes(fetch(base+name))
    name='face_detection_yunet_2023mar.onnx'
    pointer=fetch(base+name).decode('ascii')
    digest=re.search(r'oid sha256:([a-f0-9]{64})',pointer).group(1)
    size=int(re.search(r'^size (\d+)$',pointer,re.M).group(1))
    data=fetch(f'https://media.githubusercontent.com/media/opencv/opencv_zoo/{pin}/'+folder+name)
    if len(data)!=size or hashlib.sha256(data).hexdigest()!=digest:raise ValueError('YuNet model verification failed')
    (dest/name).write_bytes(data)
    report=dict(commit=pin,model=name,size=size,sha256=digest,license='MIT',identity_recognition=False)
    (dest/'provenance.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))

if __name__=='__main__':main()
