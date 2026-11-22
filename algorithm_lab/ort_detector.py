"""CUDA adapter for the same hash-verified Apache-2.0 OpenCV Zoo YOLOX model.

Pre/post-processing follows vendor/opencv_zoo_yolox/yolox.py. Candidate filtering
before NMS avoids converting all 8400 proposals into Python lists per frame.
"""
from pathlib import Path
import hashlib,json,os,sys
import cv2 as cv
import numpy as np
import bootstrap

class OrtYoloX:
    def __init__(self,model_dir,profile=False):
        gpu=bootstrap.ROOT/'tmp/algorithm_gpu_deps'
        if not (gpu/'onnxruntime').exists():raise RuntimeError('GPU runtime not installed')
        sys.path.insert(0,str(gpu))
        import onnxruntime as ort
        if 'CUDAExecutionProvider' not in ort.get_available_providers():raise RuntimeError('CUDA provider is unavailable')
        dlls=Path.home()/'Documents/ChatGPT/大学课堂/work/yolo_trial/.venv/Lib/site-packages/torch/lib'
        self.dll_handles=[os.add_dll_directory(str(dlls))]
        ort.preload_dlls(directory=str(dlls))
        manifest=json.loads((model_dir/'provenance.json').read_text(encoding='utf-8'))
        model=model_dir/manifest['model']
        if hashlib.sha256(model.read_bytes()).hexdigest()!=manifest['sha256']:
            raise ValueError('Model fingerprint changed')
        options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
        options.enable_profiling=profile
        self.session=ort.InferenceSession(model.read_bytes(),sess_options=options,
            providers=[('CUDAExecutionProvider',{'cudnn_conv_algo_search':'HEURISTIC',
                'gpu_mem_limit':2*1024**3,'do_copy_in_default_stream':True}),'CPUExecutionProvider'])
        if self.session.get_providers()[0]!='CUDAExecutionProvider':raise RuntimeError('CUDA session creation fell back to CPU')
        self.input=self.session.get_inputs()[0].name
        self.confThreshold=.45;self.nmsThreshold=.5
        grids=[];strides=[]
        for stride in [8,16,32]:
            xv,yv=np.meshgrid(np.arange(640//stride),np.arange(640//stride))
            grid=np.stack((xv,yv),2).reshape(-1,2)
            grids.append(grid);strides.append(np.full((len(grid),1),stride))
        self.grids=np.concatenate(grids).astype(np.float32)
        self.strides=np.concatenate(strides).astype(np.float32)
        self.backend='onnxruntime_cuda'
        self.version=ort.__version__

    def infer(self,image):
        blob=np.ascontiguousarray(image.transpose(2,0,1)[None],dtype=np.float32)
        outputs=self.session.run(None,{self.input:blob})[0][0]
        if outputs.shape!=(8400,85) or not np.isfinite(outputs).all():
            raise ValueError('YOLOX output shape/values changed')
        scores=outputs[:,4:5]*outputs[:,5:]
        classes=np.argmax(scores,axis=1)
        confidence=scores[np.arange(len(scores)),classes]
        selected=confidence>self.confThreshold
        if not selected.any():return np.empty((0,6),np.float32)
        d=outputs[selected,:4].copy()
        d[:,:2]=(d[:,:2]+self.grids[selected])*self.strides[selected]
        d[:,2:4]=np.exp(d[:,2:4])*self.strides[selected]
        d[:,:2]-=d[:,2:4]/2
        confidence=confidence[selected];classes=classes[selected]
        keep=cv.dnn.NMSBoxesBatched(d.tolist(),confidence.tolist(),classes.tolist(),self.confThreshold,self.nmsThreshold)
        if len(keep)==0:return np.empty((0,6),np.float32)
        return np.column_stack((d,confidence,classes))[keep]
