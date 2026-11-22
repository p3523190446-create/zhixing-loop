"""Exercise the real portable parser with valid/malformed/stale sensor streams."""
from pathlib import Path
import json
import subprocess

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'知行回路软件/board/r1_line_tracking'
OUT=ROOT/'知行回路软件/build/r1_line_tracking'
OUT.mkdir(parents=True,exist_ok=True)
test=r'''
#include "line_protocol.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void feed(line_protocol_t *p,const char *s,unsigned now) {
    while(*s)line_protocol_byte(p,(unsigned char)*s++,now);
}
int main(void) {
    line_protocol_t p={0};unsigned n;
    const char *a="$A,x1:0,x2:1,x3:4095,x4:4096,x5:65535,x6:12,x7:23,x8:34#";
    const char *d="$D,x1:0,x2:1,x3:0,x4:1,x5:0,x6:1,x7:0,x8:1#";
    assert(!line_protocol_fresh(0,0,0));
    feed(&p,"boot garbage\r\n",1);assert(!p.analog_frames && !p.digital_frames);
    feed(&p,a,100);assert(p.analog_frames==1 && p.analog[4]==65535 && p.analog[7]==34);
    feed(&p,d,101);assert(p.digital_frames==1 && p.digital[1]==1 && p.digital[6]==0);
    assert(line_protocol_fresh(p.analog_frames,p.analog_ms,599));
    assert(!line_protocol_fresh(p.analog_frames,p.analog_ms,600));
    assert(line_protocol_fresh(p.digital_frames,p.digital_ms,600));
    feed(&p,"$A,x1:10,x2:20",200);assert(p.analog_frames==1 && p.analog_ms==100);
    feed(&p,a,201);assert(p.analog_frames==2 && p.analog_ms==201 && p.rejected==1);
    n=p.rejected;
    feed(&p,"$A,x1:65536,x2:1,x3:1,x4:1,x5:1,x6:1,x7:1,x8:1#",250);
    feed(&p,"$D,x1:2,x2:1,x3:0,x4:1,x5:0,x6:1,x7:0,x8:1#",251);
    feed(&p,"$A,x2:0,x2:1,x3:1,x4:1,x5:1,x6:1,x7:1,x8:1#",252);
    feed(&p,"$A,x1:-1,x2:1,x3:1,x4:1,x5:1,x6:1,x7:1,x8:1#",253);
    feed(&p,"$A,x1:1,x2:1,x3:1,x4:1,x5:1,x6:1,x7:1,x8:1,extra#",254);
    feed(&p,"$A,x1:1,x2:1#",255);
    assert(p.rejected==n+6 && p.analog_frames==2 && p.digital_frames==1);
    feed(&p,"$A,x1:999999999999999999999999#",260);assert(p.analog_frames==2);
    feed(&p,"$A,x1:123\001",270);assert(!p.length);
    feed(&p,"$",280);for(n=0;n<200;n++)line_protocol_byte(&p,'x',280);
    assert(!p.length);feed(&p,d,281);assert(p.digital_frames==2);
    feed(&p,"$A,x1:1,x2:2",290);line_protocol_reset_frame(&p);
    feed(&p,"x3:3,x4:4,x5:5,x6:6,x7:7,x8:8#",291);assert(p.analog_frames==2);
    feed(&p,a,0xfffffff0u);
    assert(line_protocol_fresh(p.analog_frames,p.analog_ms,30));
    assert(!line_protocol_fresh(p.analog_frames,p.analog_ms,500));
    puts("PASS: actual parser valid/split/resync/reject/overflow/independent freshness/wrap");
    return 0;
}
'''
c=OUT/'line_protocol_test.c';c.write_text(test,encoding='utf-8')
exe=OUT/'line_protocol_test.exe'
cc=ROOT/'tmp/tcc-0.9.27-win64-bin/tcc/tcc.exe'
steps=[]
for args in ([cc,'-Wall','-I'+str(SOURCE),c,SOURCE/'line_protocol.c','-o',exe],[exe]):
    p=subprocess.run([str(x) for x in args],capture_output=True,text=True,timeout=30)
    steps.append(dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
    print(p.stdout+p.stderr,end='')
    if p.returncode:raise SystemExit(p.returncode)
(OUT/'parser-verification.json').write_text(json.dumps(dict(result='PASS',scope='host tests of actual C parser; no device evidence',steps=steps),indent=2)+'\n',encoding='utf-8')
