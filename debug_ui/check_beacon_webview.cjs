/** Actual K99 transport check. Malformed JSON is rejected before command routing. */
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const out=process.env.ZX_GIMBAL_CHECK_OUT;
(async()=>{
 const target=JSON.parse(fs.readFileSync(path.join(out,'phone-cdp-targets-private.json'),'utf8')).find(t=>t.type==='page');
 const ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise((ok,no)=>{ws.onopen=ok;ws.onerror=no;});
 let next=0;const pending=new Map(),errors=[],responses=[];
 ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.id&&pending.has(d.id)){const p=pending.get(d.id);pending.delete(d.id);clearTimeout(p.timer);d.error?p.no(Error(JSON.stringify(d.error))):p.ok(d.result);}else if(d.method==='Runtime.exceptionThrown')errors.push(d.params);else if(d.method==='Network.responseReceived')responses.push(d.params.response);};
 const send=(method,params={})=>new Promise((ok,no)=>{const id=++next;pending.set(id,{ok,no,timer:setTimeout(()=>no(Error(method+' timeout')),10000)});ws.send(JSON.stringify({id,method,params}));});
 const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
 try{
  await send('Runtime.enable');await send('Network.enable');errors.length=0;
  const before=await evaluate('fetch(document.body.dataset.base+"/api/status").then(r=>r.json()).then(d=>({drive:d.drive.active,gimbal:d.control.active}))');assert(!before.drive&&!before.gimbal);
  const queued=await evaluate('navigator.sendBeacon(document.body.dataset.base+"/api/gimbal-follow/stop?beacon-compat-invalid-json",new Blob(["!!"],{type:"text/plain;charset=UTF-8"}))');assert.equal(queued,true);
  for(let i=0;i<30&&!responses.some(r=>r.url.includes('beacon-compat-invalid-json'));i++)await new Promise(r=>setTimeout(r,100));
  const native=responses.find(r=>r.url.includes('beacon-compat-invalid-json'));assert(native);assert.equal(native.status,503);
  const blocked=await evaluate('fetch(document.body.dataset.base+"/api/gimbal-follow/start",{method:"POST",headers:{"Content-Type":"text/plain"},body:"{}"}).then(r=>r.status)');assert.equal(blocked,403);
  const ui=await evaluate('({steps:["followReadyBoard","followReadyTarget","followReadyGimbal","followReadyConfirm"].map(id=>document.getElementById(id).textContent)})');assert.equal(ui.steps.length,4);
  const after=await evaluate('fetch(document.body.dataset.base+"/api/status").then(r=>r.json()).then(d=>({drive:d.drive.active,gimbal:d.control.active,calibration:d.control.calibration}))');assert(!after.drive&&!after.gimbal);assert.equal(errors.length,0);
  const report={actual_phone_webview:true,external_browser_opened:false,native_beacon_queued:queued,invalid_json_rejected_before_command:native.status,text_plain_start_rejected:blocked,steps:ui.steps,state:after,uncaught_js_errors:errors,actuator_commands_sent:false,physical_tracking_tested:false};
  fs.writeFileSync(path.join(out,'beacon-phone-check.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{ws.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
