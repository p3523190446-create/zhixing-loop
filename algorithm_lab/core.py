"""Read-only algorithm proposals. This module has no serial or HTTP write API."""
import math
import time

WHITE = [220, 246, 251, 248, 249, 258, 258, 226]
BLACK = [3145, 3452, 3456, 3414, 3331, 3352, 3357, 2969]

def finite(value):
    return type(value) in (int, float) and math.isfinite(value)

class LineFollower:
    """Pololu-style weighted position and PD, in sensor coordinates only.

    Gains are experiment defaults; X1/X8 have NOT been mapped to vehicle turns.
    A wide patch or a junction stops the proposal rather than choosing a path.
    """
    def __init__(self):
        self.previous = None

    def update(self, status, now=None):
        now = time.monotonic() if now is None else now
        p = status.get('line') or {}
        raw, mask, age = p.get('raw'), p.get('digital_mask'), p.get('age_ms')
        result = dict(valid=False, state='offline', position=None, correction=None,
                      actuation_enabled=False, coordinate='X1_to_X8', age_ms=age)
        if (not status.get('connected') or not p.get('valid') or not finite(age)
                or not 0 <= age < 500 or not isinstance(raw, list) or len(raw) != 8
                or any(not finite(x) or not 0 <= x <= 65535 for x in raw)
                or type(mask) is not int or not 0 <= mask <= 255):
            self.previous = None
            return result
        dark = [not bool(mask & (1 << i)) for i in range(8)]
        strengths = [max(0., min(1., (x-WHITE[i])/(BLACK[i]-WHITE[i]))) for i,x in enumerate(raw)]
        count = sum(dark)
        segments = sum(v and (i == 0 or not dark[i-1]) for i,v in enumerate(dark))
        state = ('no_line' if count == 0 else 'all_black' if count == 8 else
                 'junction' if segments > 1 or count > 4 else 'line')
        result.update(valid=True, state=state, dark=dark, strengths=strengths, raw=raw)
        if state != 'line':
            self.previous = None
            return result
        weights = [max(.01, s) if d else 0 for s,d in zip(strengths,dark)]
        position = sum(w * (2*i/7-1) for i,w in enumerate(weights))/sum(weights)
        stamp = p.get('analog_frames')
        derivative = 0.
        if self.previous:
            old_position, old_time, old_stamp, old_correction = self.previous
            if stamp is not None and stamp == old_stamp:
                return dict(result, position=position, correction=old_correction)
            dt = now - old_time
            if 0.02 <= dt <= .5:
                derivative = (position-old_position)/dt
        correction = max(-1., min(1., .45*position + .04*derivative))
        self.previous = (position, now, stamp, correction)
        return dict(result, position=position, correction=correction)

class Vision:
    def __init__(self, model_dir=None,backend='auto'):
        import cv2 as cv
        self.cv = cv
        cv.setNumThreads(4)
        self.detector = cv.aruco.ArucoDetector(
            cv.aruco.getPredefinedDictionary(cv.aruco.DICT_APRILTAG_36h11),
            cv.aruco.DetectorParameters())
        self.previous_gray = None
        self.previous_at = None
        self.model = None
        self.model_error = None
        self.backend='none';self.gpu_error=None
        self.face_enabled=False;self.face_detector=None;self.face_error=None
        if model_dir:
            try:
                import hashlib, importlib.util, json
                from pathlib import Path
                provenance = json.loads((model_dir/'provenance.json').read_text(encoding='utf-8'))
                path = model_dir/provenance['model']
                if hashlib.sha256(path.read_bytes()).hexdigest() != provenance['sha256']:
                    raise ValueError('Model fingerprint changed')
                # OpenCV's Windows filename API cannot open this Chinese workspace
                # path. Keep a hash-verified ASCII cache for the unchanged upstream
                # loader. All image I/O below uses Python bytes instead of paths.
                cache=Path.home()/'.cache/zhixing-algorithm-models'
                cache.mkdir(parents=True,exist_ok=True)
                model=cache/(provenance['sha256']+'.onnx')
                if not model.exists() or hashlib.sha256(model.read_bytes()).hexdigest()!=provenance['sha256']:
                    temp=model.with_suffix('.tmp')
                    temp.write_bytes(path.read_bytes());temp.replace(model)
                source = model_dir/'yolox.py'
                if hashlib.sha256(source.read_bytes()).hexdigest() != provenance['source_files']['yolox.py']:
                    raise ValueError('Upstream detector source changed')
                spec = importlib.util.spec_from_file_location('zhixing_upstream_yolox', source)
                mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
                if backend in ('auto','cuda'):
                    try:
                        from ort_detector import OrtYoloX
                        self.model=OrtYoloX(model_dir)
                        self.backend='onnxruntime_cuda'
                    except Exception as error:
                        self.gpu_error=str(error)
                        if backend=='cuda':raise
                if self.model is None:
                    self.model = mod.YoloX(str(model), confThreshold=.45)
                    self.backend='opencv_cpu'
            except Exception as error:
                self.model_error = str(error)

    def process(self, image, now=None):
        import numpy as np
        cv = self.cv
        now = time.monotonic() if now is None else now
        h,w = image.shape[:2]
        drawn = image.copy()
        stages={};started_stage=time.perf_counter()
        # Keep the human preview at 960 pixels, but do color/tag work at 640.
        # All geometry is mapped back to the original image before publication.
        work=image if w<=640 else cv.resize(image,(640,round(h*640/w)),interpolation=cv.INTER_AREA)
        wh,ww=work.shape[:2];sx,sy=w/ww,h/wh
        hsv = cv.cvtColor(work, cv.COLOR_BGR2HSV)
        colors = []
        for name,lo,hi in [('red',(0,110,80),(10,255,255)),
                           ('green',(40,90,70),(85,255,255)),
                           ('blue',(95,100,60),(130,255,255))]:
            mask = cv.inRange(hsv, np.array(lo), np.array(hi))
            if name == 'red':
                mask |= cv.inRange(hsv, np.array((170,110,80)), np.array((179,255,255)))
            mask = cv.morphologyEx(mask, cv.MORPH_OPEN, np.ones((3,3),np.uint8))
            contours,_ = cv.findContours(mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
            if not contours: continue
            contour = max(contours,key=cv.contourArea)
            area = cv.contourArea(contour)
            if area < max(80, ww*wh*.002): continue
            x,y,bw,bh = cv.boundingRect(contour)
            x,y,bw,bh=round(x*sx),round(y*sy),round(bw*sx),round(bh*sy)
            target = dict(color=name, bbox=[x,y,bw,bh], area_fraction=area/(ww*wh),
                          offset_x=(x+bw/2)/(w/2)-1, offset_y=(y+bh/2)/(h/2)-1)
            colors.append(target)
            cv.rectangle(drawn,(x,y),(x+bw,y+bh),(0,215,255),2)
            cv.putText(drawn,name,(x,max(15,y-4)),cv.FONT_HERSHEY_SIMPLEX,.5,(0,215,255),1)
        stages['color_ms']=round((time.perf_counter()-started_stage)*1000,2)
        started_stage=time.perf_counter()
        gray = cv.cvtColor(work,cv.COLOR_BGR2GRAY)
        corners,ids,_ = self.detector.detectMarkers(gray)
        tags = []
        if ids is not None:
            corners=[p*np.array((sx,sy),np.float32) for p in corners]
            cv.aruco.drawDetectedMarkers(drawn,corners,ids)
            for points,ident in zip(corners,ids.flatten()):
                tags.append(dict(id=int(ident), corners=points[0].tolist(), station_arrived=False))
        stages['tags_ms']=round((time.perf_counter()-started_stage)*1000,2)
        started_stage=time.perf_counter()
        faces=[]
        if self.face_enabled:
            try:
                if self.face_detector is None:
                    from pathlib import Path
                    import hashlib,json
                    folder=Path(__file__).resolve().parent/'vendor/opencv_zoo_yunet'
                    provenance=json.loads((folder/'provenance.json').read_text(encoding='utf-8'))
                    data=(folder/provenance['model']).read_bytes()
                    if hashlib.sha256(data).hexdigest()!=provenance['sha256']:raise ValueError('YuNet fingerprint changed')
                    cache=Path.home()/'.cache/zhixing-algorithm-models'
                    cache.mkdir(parents=True,exist_ok=True)
                    path=cache/(provenance['sha256']+'.onnx')
                    if not path.exists():path.write_bytes(data)
                    elif hashlib.sha256(path.read_bytes()).hexdigest()!=provenance['sha256']:raise ValueError('YuNet cache changed')
                    self.face_detector=cv.FaceDetectorYN.create(str(path),'',(320,256),score_threshold=.85)
                face_image=cv.resize(image,(320,256))
                _,detected=self.face_detector.detect(face_image)
                if detected is not None:
                    for item in detected:
                        x,y,bw,bh=item[:4]*np.array((w/320,h/256,w/320,h/256),np.float32)
                        box=list(map(float,(x,y,bw,bh)))
                        faces.append(dict(bbox=box,score=float(item[-1])))
                        x,y,bw,bh=map(round,box)
                        cv.rectangle(drawn,(x,y),(x+bw,y+bh),(220,100,255),2)
                self.face_error=None
            except Exception as error:self.face_error=str(error)
        stages['face_ms']=round((time.perf_counter()-started_stage)*1000,2)
        started_stage=time.perf_counter()
        small = cv.resize(gray,(160,120))
        small = cv.GaussianBlur(small,(5,5),0)
        motion = None
        if self.previous_gray is not None and 0 < now-self.previous_at <= 2:
            diff = cv.absdiff(small,self.previous_gray)
            motion = float(np.mean(diff > 25))
        self.previous_gray,self.previous_at = small,now
        stages['motion_ms']=round((time.perf_counter()-started_stage)*1000,2)
        objects = []
        inference_ms = None
        model_error = self.model_error
        if self.model:
            started = time.perf_counter()
            ratio = min(640/h,640/w)
            padded = np.full((640,640,3),114,dtype=np.float32)
            resized = cv.resize(image,(int(w*ratio),int(h*ratio))).astype(np.float32)
            padded[:resized.shape[0],:resized.shape[1]] = resized
            try:
                detections = self.model.infer(padded)
                for d in detections:
                    x,y,bw,bh = (d[:4]/ratio).tolist()
                    x1,y1 = max(0,min(w,round(x))),max(0,min(h,round(y)))
                    x2,y2 = max(0,min(w,round(x+bw))),max(0,min(h,round(y+bh)))
                    if x2 <= x1 or y2 <= y1: continue
                    ident,score = int(d[-1]),float(d[-2])
                    objects.append(dict(class_id=ident,score=score,bbox=[x1,y1,x2-x1,y2-y1]))
                    cv.rectangle(drawn,(x1,y1),(x2,y2),(110,255,100),2)
                    cv.putText(drawn,f'#{ident} {score:.0%}',(x1,max(15,y1-5)),cv.FONT_HERSHEY_SIMPLEX,.5,(110,255,100),1)
            except Exception as error:
                model_error = str(error)
            inference_ms = round((time.perf_counter()-started)*1000,1)
        cv.drawMarker(drawn,(w//2,h//2),(220,220,220),cv.MARKER_CROSS,20,1)
        return dict(colors=colors,tags=tags,objects=objects,faces=faces,face_enabled=self.face_enabled,
                    face_model_loaded=self.face_detector is not None,face_error=self.face_error,motion_fraction=motion,
                    motion_event=motion is not None and motion > .08,
                    motion_note='画面变化可能由相机移动或光照造成',
                    model_loaded=self.model is not None,model_error=model_error,inference_ms=inference_ms,
                    backend=self.backend,gpu_error=self.gpu_error,
                    stage_ms=stages,working_resolution=[ww,wh],
                    actuation_enabled=False),drawn
