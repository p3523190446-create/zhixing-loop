"""Read only this debug app's own retained probe logs using authorized ADB."""
from pathlib import Path
import base64,io,json,subprocess,tarfile,time
root=Path(__file__).resolve().parents[2]
adb=root/'tmp/android-tools/platform-tools/adb.exe'
result=subprocess.run([str(adb),'exec-out','run-as','cn.zhixing.boardlinkprobe','tar','-cf','-','files/board-link','files/board-link-ui.jsonl'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
out=root/'output/phone_board_link'/('readback-'+time.strftime('%Y%m%d-%H%M%S'));out.mkdir(parents=True)
with tarfile.open(fileobj=io.BytesIO(result.stdout),mode='r:') as archive:
    for member in archive.getmembers():
        target=out/member.name
        if not target.resolve().is_relative_to(out.resolve()) or not member.isfile():continue
        if member.size>32*1024*1024:raise ValueError('Unexpected probe file size')
        target.parent.mkdir(parents=True,exist_ok=True)
        with archive.extractfile(member) as source:target.write_bytes(source.read())
summary=[]
allowed={b'PING\n',b'STATUS\n',b'GIMBAL_STATUS\n',b'ULTRA_STATUS\n'}
echo_allowed={b'ZX_LOOP_A01\n',b'ZX_LOOP_B02\n',b'ZX_LOOP_C03\n'}
native_allowed={b'PING\n',b'NATIVE_ID\n',b'ZX_NATIVE_A01\n',b'ZX_NATIVE_B02\n',b'ZX_NATIVE_C03\n'}
for session in sorted((out/'files/board-link').iterdir()):
    events=[];truncated=False
    for line in (session/'events.jsonl').read_text(encoding='utf-8').splitlines():
        try:events.append(json.loads(line))
        except ValueError:truncated=True;break
    assert [e['seq'] for e in events]==list(range(1,len(events)+1))
    assert all(a['elapsed_ns']<=b['elapsed_ns'] for a,b in zip(events,events[1:]))
    for e in events:
        if e['event']!='uart_bytes':continue
        raw=base64.b64decode(e['data_b64'],validate=True);assert len(raw)==e['length']
        if e['direction']=='TX_ATTEMPT':assert raw in ((allowed|{b'NATIVE_FEATURES\n'}) if events[0].get('mode')=='NATIVE_TELEMETRY' else native_allowed if events[0].get('mode')=='NATIVE_USBFS' else echo_allowed if events[0].get('mode')=='WCH_LOOPBACK' else allowed)
    end=[e for e in events if e['event']=='session_finished']
    try:meta=json.loads((session/'result.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):meta=None
    error=any(e['event'] in ('session_error','reader_error') for e in events)
    complete=bool(end and meta and not truncated and not error)
    summary.append({'session':session.name,'mode':events[0].get('mode','UNKNOWN') if events else 'UNKNOWN','events':len(events),'state':'ERROR' if error or (meta and not meta.get('passed')) else 'COMPLETE' if complete else 'INTERRUPTED','passed':bool(complete and end[-1]['passed'] and meta.get('passed')),'replies':sum(e['event']=='query_reply' for e in events)})
(out/'verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
audit=[json.loads(line) for line in (out/'files/board-link-ui.jsonl').read_text(encoding='utf-8').splitlines()]
print(json.dumps({'folder':str(out),'total_sessions':len(summary),'recent_sessions':summary[-5:],'ui_events':len(audit),'recent_ui':audit[-8:]},ensure_ascii=False,indent=2))
