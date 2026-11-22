"""Export this app's own retained raw journals through authorized ADB."""
from pathlib import Path
import subprocess,tarfile,io,time,json,base64
root=Path(__file__).resolve().parents[2];adb=root/'tmp/android-tools/platform-tools/adb.exe'
packed=subprocess.run([str(adb),'exec-out','run-as','cn.zhixing.carconsole','tar','-cf','-','files'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout
out=root/'output/car_phone'/('readback-'+time.strftime('%Y%m%d-%H%M%S'));out.mkdir(parents=True)
with tarfile.open(fileobj=io.BytesIO(packed),mode='r:') as tar:
    for m in tar.getmembers():
        target=out/m.name
        if not m.isfile() or not target.resolve().is_relative_to(out.resolve()):continue
        if m.size>256*1024*1024:raise ValueError('Unexpected journal size')
        target.parent.mkdir(parents=True,exist_ok=True)
        with tar.extractfile(m) as f:target.write_bytes(f.read())
allowed={x+b'\n' for x in [b'NATIVE_FEATURES',b'STATUS',b'ULTRA_STATUS',b'GIMBAL_STATUS',b'MUTE_STATUS',b'PARAM_STATUS',b'RECOVERY_STATUS',b'OLED_SCREEN',b'OLED2_SCREEN',b'OLED3_SCREEN',b'MOTOR_DASH_STATUS']}
sessions=out/'files/sessions';results=[]
for folder in sorted(sessions.iterdir()) if sessions.exists() else []:
    if not folder.is_dir():continue
    events=[];truncated=False
    for line in (folder/'events.jsonl').read_text(encoding='utf-8').splitlines():
        try:events.append(json.loads(line))
        except ValueError:truncated=True;break
    assert [e['seq'] for e in events]==list(range(1,len(events)+1))
    assert all(a['elapsed_ns']<=b['elapsed_ns'] for a,b in zip(events,events[1:]))
    directions={d:[] for d in ['TX_ATTEMPT','TX_ACCEPTED','RX']}
    for e in events:
        if e['event']!='uart_bytes':continue
        raw=base64.b64decode(e['data_b64'],validate=True);assert len(raw)==e['length']
        assert e['direction'] in directions;directions[e['direction']].append(raw)
        if e['direction']=='TX_ATTEMPT':assert raw in allowed
    try:end=json.loads((folder/'result.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):end=None
    rows=[e for e in events if e['event']=='query_reply'];samples=[e for e in events if e['event']=='sample_complete']
    statuses=[list(map(int,e['line'].split(',')[1:])) for e in rows if e['command']=='STATUS']
    freshness=bool(len(statuses)>=2 and all(a[0]<b[0] and a[1]<b[1] for a,b in zip(statuses,statuses[1:])))
    finish=[e for e in events if e['event']=='session_finished'];errors=[e for e in events if e['event'] in ('session_error','reader_error')]
    closed=bool(end and end['clean_close'] and finish and not errors and not truncated)
    if end and closed:assert end['events']==len(events) and end['queries']==len(rows) and end['cycles']==len(samples)
    intervals=[];away=None
    for e in events:
        if e['event']!='ui_visibility':continue
        if not e['visible'] and away is None:away=e['elapsed_ns']
        elif e['visible'] and away is not None:intervals.append((away,e['elapsed_ns']));away=None
    background_seconds=sum((b-a)/1e9 for a,b in intervals)
    background_queries=sum(any(a<=e['elapsed_ns']<=b for a,b in intervals) for e in rows)
    replies_raw=(b''.join(directions['RX'])).split(b'\n');reply_lines=[e['line'].encode() for e in rows]
    # Strictly parsed query lines must be present in the unmodified packet stream.
    cursor=0
    for line in reply_lines:
        while cursor<len(replies_raw) and replies_raw[cursor]!=line:cursor+=1
        assert cursor<len(replies_raw),'Parsed reply absent from raw RX';cursor+=1
    result=dict(session=folder.name,version=events[0].get('version') if events else None,clean_close=closed,cycles=len(samples),queries=len(rows),fresh_uptime_and_range_rounds=freshness,
        raw_tx_bytes=sum(map(len,directions['TX_ACCEPTED'])),raw_rx_bytes=sum(map(len,directions['RX'])),
        elapsed_seconds=(events[-1]['elapsed_ns']-events[0]['elapsed_ns'])/1e9 if events else 0,reason=end.get('reason') if end else None,
        errors=errors,background_seconds=background_seconds,background_queries=background_queries,
        empty_completions=sum(e['event']=='usb_empty_completion' for e in events),
        raw_scope='Allowlisted read queries and exact bytes; physical motion not exercised')
    results.append(result)
(out/'verification.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'folder':str(out),'sessions':results},ensure_ascii=False,indent=2))
