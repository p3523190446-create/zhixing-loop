"""Verify the real phone's VLM config validation, without changing valid config."""
from pathlib import Path
import json
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'output/onboard_dashboard/large-vision-20261107'
source = json.loads((OUT/'lan-source-private.json').read_text(encoding='utf-8'))['url']
p = urlsplit(source)
opener = build_opener(ProxyHandler({}))
before = json.load(opener.open(source+'/api/vlm/settings', timeout=4))
cases = [{'url': ''}, {'url': 'https://example.com/models'},
         {'url': 'http://8.8.8.8:8797/abcdefghijklmnopqrstuvwxyz'},
         {'url': 'http://192.168.43.5:8797/short'}, {'url': before['url'], 'extra': True}]
report = []
for n, case in enumerate(cases):
    request = Request(source+'/api/vlm/settings', data=json.dumps(case).encode(),
                      headers={'Origin': p.scheme+'://'+p.netloc, 'Content-Type': 'application/json'})
    try:
        response = opener.open(request, timeout=4)
        raise AssertionError('Invalid model address was accepted')
    except HTTPError as error:
        assert error.code == 400
        report.append({'case': n, 'status': error.code})
after = json.load(opener.open(source+'/api/vlm/settings', timeout=4))
assert after == before
result = {'rejected_cases': report, 'valid_configuration_preserved': True, 'actuator_requests': 0}
(OUT/'shared-settings-validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result))
