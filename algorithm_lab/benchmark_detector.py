"""Same input/model CPU-CUDA comparison, parity and executed-provider evidence."""
import bootstrap
from pathlib import Path
import json,time,statistics
import cv2 as cv
import numpy as np
from core import Vision
from ort_detector import OrtYoloX

def main():
    here=Path(__file__).resolve().parent
    out=bootstrap.ROOT/'output/onboard_dashboard/algorithm-optimization-20261025'
    out.mkdir(parents=True,exist_ok=True)
    image=Path.home()/'Documents/ChatGPT/大学课堂/work/yolo_trial/bus.jpg'
    image=cv.imdecode(np.frombuffer(image.read_bytes(),np.uint8),cv.IMREAD_COLOR)
    h,w=image.shape[:2];r=min(640/h,640/w)
    padded=np.full((640,640,3),114,np.float32)
    resized=cv.resize(image,(int(w*r),int(h*r))).astype(np.float32)
    padded[:resized.shape[0],:resized.shape[1]]=resized
    cpu=Vision(here/'vendor/opencv_zoo_yolox',backend='cpu').model
    gpu=OrtYoloX(here/'vendor/opencv_zoo_yolox',profile=True)
    results={};detections={}
    for name,model in [('cpu',cpu),('cuda',gpu)]:
        for _ in range(3):model.infer(padded.copy())
        elapsed=[]
        for _ in range(20):
            started=time.perf_counter();d=model.infer(padded.copy());elapsed.append((time.perf_counter()-started)*1000)
        detections[name]=d.tolist()
        results[name]=dict(median_ms=statistics.median(elapsed),p95_ms=sorted(elapsed)[18],count=len(d),samples_ms=elapsed)
    for a in detections['cpu']:
        matches=[b for b in detections['cuda'] if int(a[-1])==int(b[-1]) and abs(a[-2]-b[-2])<.01 and max(abs(x-y) for x,y in zip(a[:4],b[:4]))<2]
        assert matches,'CUDA detection changed beyond this parity tolerance'
    profile=Path(gpu.session.end_profiling())
    events=json.loads(profile.read_text(encoding='utf-8'))
    providers={}
    for event in events:
        provider=event.get('args',{}).get('provider')
        if provider:providers[provider]=providers.get(provider,0)+1
    assert providers.get('CUDAExecutionProvider',0)>0
    (out/'ort-profile.json').write_bytes(profile.read_bytes())
    report=dict(same_model=True,same_input=True,parity_pass=True,results=results,
                executed_providers=providers,ort_version=gpu.version,
                actual_cuda_used=True,actuation_enabled=False)
    (out/'detector-benchmark.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))

if __name__=='__main__':main()
