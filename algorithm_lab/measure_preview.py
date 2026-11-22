"""Measure frames actually received from the independent local MJPEG endpoint."""
import bootstrap
import json,time,urllib.request
from server import OUT,timestamp

def main():
    frames=[]
    with urllib.request.urlopen('http://127.0.0.1:8796/preview.mjpeg',timeout=5) as response:
        boundary=response.readline()
        while len(frames)<46:
            if boundary.strip()!=b'--zhixingframe':raise ValueError('Bad MJPEG boundary')
            headers={}
            while True:
                line=response.readline()
                if line==b'\r\n':break
                key,value=line.decode('ascii').split(':',1);headers[key.lower()]=value.strip()
            length=int(headers['content-length'])
            if not 0<length<4*1024*1024:raise ValueError('Bad JPEG length')
            frame=response.read(length)
            if len(frame)!=length or not frame.startswith(b'\xff\xd8') or not frame.endswith(b'\xff\xd9'):
                raise ValueError('Invalid complete preview frame')
            frames.append(dict(received_monotonic=time.monotonic(),seq=int(headers['x-frame-seq']),bytes=length))
            if response.read(2)!=b'\r\n':raise ValueError('Bad part delimiter')
            boundary=response.readline()
    seconds=frames[-1]['received_monotonic']-frames[0]['received_monotonic']
    fps=(len(frames)-1)/seconds
    with urllib.request.urlopen('http://127.0.0.1:8796/api/status',timeout=4) as response:d=json.load(response)
    assert d['vision_valid'] and d['model_ready']
    assert d['actuation_enabled'] is False
    assert (d['camera_source']['width'],d['camera_source']['height'])==(960,768)
    assert fps>10,'Preview did not meet this round\'s 10fps minimum'
    report=dict(at=timestamp(),mode='REAL_BORROWED_CAMERA_HTTP_RECEIPT',frames=len(frames),
        elapsed_s=seconds,received_fps=fps,camera=d['camera_source'],detection_fps=d.get('detection_fps'),
        inference_ms=d['vision']['inference_ms'],frame_samples=frames,
        camera_to_action_latency_verified=False,actuation_enabled=False)
    (OUT/'preview-performance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['frames','elapsed_s','received_fps','detection_fps','inference_ms']}))

if __name__=='__main__':main()
