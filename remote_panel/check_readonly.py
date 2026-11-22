"""Verify live HTTP and stale data without opening serial or moving wheels."""
from pathlib import Path
import json, urllib.request, urllib.error, time
import server

here=Path(__file__).resolve().parent
runtime=json.loads((here/'runtime.json').read_text(encoding='utf-8'))
url=runtime['url']
def request(url, method='GET'):
    try:
        with urllib.request.urlopen(urllib.request.Request(url,method=method),timeout=5) as r:
            return r.status,r.read()
    except urllib.error.HTTPError as e:
        return e.code,e.read()

code,page=request(url)
assert code==200 and '小车状态'.encode() in page
code,raw=request(url+'api/status');a=json.loads(raw)
assert code==200 and a['connected'] and a['age_ms']<5000
time.sleep(2)
code,raw=request(url+'api/status');b=json.loads(raw)
assert code==200 and b['connected'] and b['uptime_s']>a['uptime_s']
assert request(url+'api/status','POST')[0]==405
assert request(url+'unknown')[0]==404
server.latest={'connected':True,'received_monotonic':10,'distance_mm':200,
               'voltage_mv':8100,'wheel_speeds_mm_s':[0,0,0,0],
               'motion_active':False,'motor_fault':0,'range_valid':True}
stale=server.public_state(now=16)
assert not stale['connected'] and not stale['range_valid']
assert all(stale[k] is None for k in ('distance_mm','voltage_mv','wheel_speeds_mm_s','motion_active','motor_fault'))
report={'result':'PASS_READONLY_HTTP_FRESHNESS_AND_STALE_MASKING',
        'checked_at':server.datetime.now(server.timezone.utc).isoformat(),
        'snapshots':[a,b],'POST':405,'unknown_path':404,
        'serial_opened_by_check':False,'motion_commands':'NONE',
        'phone_network_acceptance':'PENDING_USER_TEST','visual_layout':'NOT_INSPECTED'}
(here/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
