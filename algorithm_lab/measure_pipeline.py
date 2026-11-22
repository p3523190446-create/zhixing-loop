"""Real preview/result stream throughput and host-reception age, not exposure latency."""
import bootstrap
from pathlib import Path
import json,time,urllib.request,statistics

OUT=bootstrap.ROOT/'output/onboard_dashboard/algorithm-optimization-20261025'

def measure(endpoint,count=91):
    rows=[]
    with urllib.request.urlopen('http://127.0.0.1:8796/'+endpoint,timeout=6) as response:
        boundary=response.readline()
        while len(rows)<count:
            if boundary.strip()!=b'--zhixingframe':raise ValueError('Bad MJPEG boundary')
            headers={}
            while True:
                line=response.readline()
                if line==b'\r\n':break
                key,value=line.decode('ascii').split(':',1);headers[key.lower()]=value.strip()
            size=int(headers['content-length'])
            if not 0<size<4*1024*1024:raise ValueError('Bad JPEG length')
            frame=response.read(size);received=time.monotonic()
            if len(frame)!=size or not frame.startswith(b'\xff\xd8') or not frame.endswith(b'\xff\xd9'):
                raise ValueError('Incomplete JPEG')
            source=int(headers['x-source-received-ns'])/1e9
            rows.append(dict(seq=headers['x-frame-seq'],at=received,host_age_ms=(received-source)*1000,bytes=size))
            if response.read(2)!=b'\r\n':raise ValueError('Bad delimiter')
            boundary=response.readline()
    duration=rows[-1]['at']-rows[0]['at'];ages=sorted(r['host_age_ms'] for r in rows)
    return dict(frames=len(rows),duration_s=duration,fps=(len(rows)-1)/duration,
        host_age_median_ms=statistics.median(ages),host_age_p95_ms=ages[int(len(ages)*.95)],samples=rows)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    results={endpoint:measure(endpoint) for endpoint in ['preview.mjpeg','detection.mjpeg']}
    statuses=[]
    for _ in range(20):
        with urllib.request.urlopen('http://127.0.0.1:8796/api/status',timeout=3) as response:d=json.load(response)
        assert d['model_backend']=='onnxruntime_cuda' and d['vision_valid']
        assert not d['telemetry']['drive']['active'] and d['telemetry']['speed_targets']==[0,0,0,0]
        statuses.append(d);time.sleep(.1)
    assert results['preview.mjpeg']['fps']>25
    assert results['detection.mjpeg']['fps']>15
    report=dict(mode='REAL_BORROWED_USB031',results=results,statuses=statuses,
        source_age_definition='From decoded JPEG publication in the PC capture thread to local HTTP client receipt.',
        exposure_to_screen_latency_verified=False,gimbal_motion=False,vehicle_motion=False)
    (OUT/'live-pipeline-performance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({name:{k:v for k,v in r.items() if k!='samples'} for name,r in results.items()}))

if __name__=='__main__':main()
