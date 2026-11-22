"""Check inference on an existing course image and archived real camera frames.

These are offline checks, never evidence of a currently connected camera.
"""
import bootstrap
from pathlib import Path
import hashlib,json,time
import cv2 as cv
import numpy as np
from core import Vision

HERE=Path(__file__).resolve().parent
ROOT=bootstrap.ROOT
OUT=ROOT/'output/onboard_dashboard/algorithms-20261025'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    vision=Vision(HERE/'vendor/opencv_zoo_yolox')
    if vision.model is None:raise RuntimeError(vision.model_error)
    results=[]
    def check(name,raw,kind):
        image=cv.imdecode(np.frombuffer(raw,np.uint8),cv.IMREAD_COLOR)
        if image is None:raise ValueError('Bad input image')
        if image.shape[1]>1280:image=cv.resize(image,(1280,round(image.shape[0]*1280/image.shape[1])))
        started=time.monotonic();d,drawn=vision.process(image)
        ok,encoded=cv.imencode('.jpg',drawn)
        if not ok:raise ValueError('JPEG encoding failed')
        (OUT/(name+'.jpg')).write_bytes(encoded.tobytes())
        results.append(dict(name=name,input_kind=kind,input_sha256=hashlib.sha256(raw).hexdigest(),
            processing_ms=round((time.monotonic()-started)*1000,2),result=d))
    course=Path.home()/'Documents/ChatGPT/大学课堂/work/yolo_trial/bus.jpg'
    if course.exists():check('course-bus-offline',course.read_bytes(),'existing_course_sample_not_live')
    rec=ROOT/'知行回路软件/remote_panel/recordings/20261013-111550-e5699c'
    rows=[json.loads(line) for line in (rec/'frames.jsonl').read_text(encoding='utf-8').splitlines()]
    with (rec/'video.mjpeg').open('rb') as stream:
        for index in [0,len(rows)//2,len(rows)-1]:
            row=rows[index];stream.seek(row['offset']);raw=stream.read(row['length'])
            check(f'camera-archive-{index}',raw,'real_camera_archive_2026-10-13_not_live')
    for ident in [0,1,2]:
        marker=cv.aruco.generateImageMarker(cv.aruco.getPredefinedDictionary(cv.aruco.DICT_APRILTAG_36h11),ident,400)
        marker=cv.copyMakeBorder(marker,70,70,70,70,cv.BORDER_CONSTANT,value=255)
        ok,encoded=cv.imencode('.png',marker)
        if not ok:raise ValueError('Marker PNG encoding failed')
        (OUT/f'AprilTag36h11-{ident}.png').write_bytes(encoded.tobytes())
    report=dict(mode='OFFLINE_REPLAY_ONLY',model_loaded=True,opencv=cv.__version__,
                cpu_backend=True,actuation_enabled=False,results=results,
                note='Archived frames and course sample; no current camera or physical tracking acceptance.')
    (OUT/'offline-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'mode':report['mode'],'images':len(results),
        'detections':[len(r['result']['objects']) for r in results],
        'inference_ms':[r['result']['inference_ms'] for r in results]}))

if __name__=='__main__':main()
