const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const out=path.resolve(__dirname,'../../output/onboard_dashboard/phone-live-vision-20261026');
const targets=JSON.parse(fs.readFileSync(path.join(out,'phone-cdp-targets-private.json'),'utf8'));
if(targets.length!==1)throw Error('Expected one phone WebView page');
const ws=new WebSocket(targets[0].webSocketDebuggerUrl);let id=0;const pending=new Map(),exceptions=[],writes=[];
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
ws.onmessage=event=>{const d=JSON.parse(event.data);if(d.id&&pending.has(d.id)){const p=pending.get(d.id);pending.delete(d.id);clearTimeout(p.timer);d.error?p.reject(Error(JSON.stringify(d.error))):p.resolve(d.result);}else if(d.method==='Runtime.exceptionThrown')exceptions.push(d.params);else if(d.method==='Network.requestWillBeSent'&&d.params.request.method==='POST'&&d.params.request.url.includes('/api/'))writes.push(d.params.request.url.split('/api/')[1]);};
const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id,timer=setTimeout(()=>{pending.delete(n);reject(Error(method+' timed out'));},7000);pending.set(n,{resolve,reject,timer});ws.send(JSON.stringify({id:n,method,params}));});
const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
(async()=>{
 await new Promise((resolve,reject)=>{if(ws.readyState===1)resolve();else{ws.onopen=resolve;ws.onerror=reject;}});
 try{
  await send('Runtime.enable');await send('Network.enable');
  let ready=false;for(let n=0;n<30;n++){ready=await evaluate('document.documentElement.getAttribute("data-ui-ready")==="true"');if(ready)break;await pause(100);}
  assert.equal(ready,true);
  const initial=await evaluate('({ready:document.documentElement.getAttribute("data-ui-ready"),version:document.querySelector("button").textContent,panelHidden:document.getElementById("phoneVisionPanel").hidden,defaultFps:document.getElementById("cameraFps").value,hidden:document.hidden,ua:navigator.userAgent})');
  assert.equal(initial.panelHidden,false);assert.equal(initial.defaultFps,'30');
  const info=await evaluate('fetch(document.body.dataset.base+"/api/ui/info").then(r=>r.json())');assert.equal(info.source_version,'0.25.2');assert.equal(info.local_vision,true);
  const state=()=>evaluate('fetch(document.body.dataset.base+"/api/vision/status").then(r=>r.json())');
  await evaluate('document.getElementById("phoneVisionToggle").click();true');await pause(200);assert.equal((await state()).enabled,false);
  await evaluate('document.getElementById("phoneVisionToggle").click();true');await pause(200);assert.equal((await state()).enabled,true);
  await evaluate('document.getElementById("phoneVisionMode").value="blue";document.getElementById("phoneVisionMode").dispatchEvent(new Event("change"));true');await pause(200);assert.equal((await state()).mode,'blue');
  await evaluate('document.getElementById("phoneVisionMode").value="red";document.getElementById("phoneVisionMode").dispatchEvent(new Event("change"));true');await pause(200);
  const final=await state();assert.equal(final.mode,'red');assert.equal(final.actuation_enabled,false);assert.equal(final.valid,false);
  assert.equal(writes.filter(p=>p.startsWith('drive/')||p.startsWith('gimbal/')||p==='camera/start').length,0);
  assert.equal(exceptions.length,0);
  const report={actual_phone_webview:true,initial,source_version:info.source_version,local_vision_available:true,pause_resume_controls:'PASS',color_choice:'PASS',final,writes,uncaught_exceptions:exceptions,live_camera_acceptance:false};
  fs.writeFileSync(path.join(out,'actual-phone-webview-check.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{ws.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
