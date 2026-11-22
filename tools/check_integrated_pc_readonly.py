"""Real HTTP/read-only integration acceptance; only explicit zero/stop writes."""
from pathlib import Path
import hashlib,json,time,urllib.request
ROOT=Path(__file__).resolve().parents[2]
out=ROOT/'output/onboard_dashboard/integrated-v014'
origin='http://127.0.0.1:8795';base=origin+'/-EkPeOg3Z3zePaJPwNnaX0fQ'
def get(path):
    with urllib.request.urlopen(base+path,timeout=4) as r:return r.read()
def stop(area):
    req=urllib.request.Request(base+'/api/'+area+'/stop',data=b'{}',headers={'Origin':origin,'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=4) as r:return json.load(r)
result=dict(drive_stop=stop('drive'),gimbal_stop=stop('gimbal'),nonzero_writes=False,samples=[])
assert result['drive_stop']['stopped'] and result['gimbal_stop']['stopped']
for _ in range(10):
    d=json.loads(get('/api/status'));result['samples'].append(d)
    assert d['connected'] and d['demo'] is False and d['capabilities']['drive_control'] and d['capabilities']['gimbal_control']
    assert d['link_age_ms']<1000 and d['age_ms']<2500 and d['range_valid']
    assert d['applied_pwm']==d['speed_targets']==d['wheel_speeds']==[0,0,0,0]
    assert not d['drive']['active'] and not d['control']['active'] and not d['gimbal']['active']
    assert not d['capabilities']['ground_control'] and d['uart_errors']==d['uart_drops']==0
    time.sleep(1)
assert len({d['received_at'] for d in result['samples']})>=5
for path in ['/desktop','/mobile','/speed','/assets/features/drive.js','/api/ui/info','/api/camera/status','/api/record/status','/api/record/list','/api/photo/list']:assert get(path)
meta=json.loads((out/'android-build-result.json').read_text(encoding='utf8'))
result['apk_download_sha256']=hashlib.sha256(get('/update.apk')).hexdigest()
assert result['apk_download_sha256']==meta['sha256']
log=(out/'browser-check.log').read_text(encoding='utf-8-sig')
browser=json.loads(log.split('### Result\n',1)[1].split('\n### Ran',1)[0]);assert all(c['pass'] for c in browser['checks'])
(out/'browser-checks.json').write_text(json.dumps(browser,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
result['status']='PASS'
(out/'pc-live-readonly-checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(status='PASS',real_samples=len(result['samples']),browser_checks=len(browser['checks']),apk_sha256=result['apk_download_sha256'],nonzero_writes=False)))
