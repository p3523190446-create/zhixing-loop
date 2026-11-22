/** Exercise the actual phone WebView over its ADB-local CDP socket. */
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const root=path.resolve(__dirname,'../..');
const out=path.join(root,'output/onboard_dashboard/camera-compat-20261026/v025');
const old=fs.readFileSync(path.join(out,'before/debug_ui/assets/features/imu-observer.js'),'utf8').replace(/^export /gm,'');
const current=fs.readFileSync(path.join(__dirname,'assets/features/imu-observer.js'),'utf8').replace(/^export /gm,'');
const oldView=new Function(old+';return observerView;')(),newView=new Function(current+';return observerView;')();
const fixtures=[undefined,null,{}, {connected:false,mpu:{}}, {connected:true,mpu:{valid:true,features:{valid:true,age_ms:5,states:['low_dynamic'],vibration_rms:0.02,vibration_peak:0.04,turn_window_deg:1,shock_count:0,tilt_count:0,freefall_count:0}}}, {connected:true,mpu:{valid:true,features:{valid:true,age_ms:1500,reference_matches:true,flags:128}}}];
for(const data of fixtures)assert.deepEqual(newView(data),oldView(data));

(async()=>{
 const target=JSON.parse(fs.readFileSync(path.join(out,'phone-cdp-targets-private.json'),'utf8'))[0];
 const ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise((ok,no)=>{ws.onopen=ok;ws.onerror=no;});
 let id=0;const pending=new Map(),events=[],requests=[];
 ws.onmessage=event=>{const data=JSON.parse(event.data);if(data.id&&pending.has(data.id)){const p=pending.get(data.id);pending.delete(data.id);clearTimeout(p.timer);data.error?p.no(new Error(JSON.stringify(data.error))):p.ok(data.result);}else if(data.method==='Runtime.exceptionThrown')events.push(data.params);else if(data.method==='Network.requestWillBeSent'&&data.params.request.url.includes('/api/'))requests.push(data.params.request.url.split('/api/')[1]);};
 const send=(method,params={})=>new Promise((ok,no)=>{const n=++id,timer=setTimeout(()=>{pending.delete(n);no(new Error(method+' timeout'));},10000);pending.set(n,{ok,no,timer});ws.send(JSON.stringify({id:n,method,params}));});
 const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
 try{
  await send('Runtime.enable');
  await send('Network.enable');
  const syntax=await evaluate('(()=>{let oldError="",newError="";try{new Function('+JSON.stringify(old)+');}catch(e){oldError=String(e);}try{new Function('+JSON.stringify(current)+');}catch(e){newError=String(e);}return {oldError:oldError,newError:newError,userAgent:navigator.userAgent};})()');
  assert.match(syntax.oldError,/SyntaxError/);assert.equal(syntax.newError,'');
  const ready=await evaluate('({ready:document.documentElement.getAttribute("data-ui-ready"),cameraButtonDisabled:document.getElementById("startCamera").disabled,abortController:typeof AbortController})');
  assert.equal(ready.ready,'true');assert.equal(ready.cameraButtonDisabled,false);assert.equal(ready.abortController,'function');
  const before=await evaluate('fetch(document.body.dataset.base+"/api/camera/compatibility").then(r=>r.json())');
  assert.equal(before.camera_candidates,0,'Missing-device UI check requires no attached camera');
  assert.equal(await evaluate('document.hidden'),false,'Actual page interaction requires visible WebView');
  await evaluate('fetch(document.body.dataset.base+"/api/camera/stop",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}).then(r=>r.json())');
  requests.length=0;
  await evaluate('document.getElementById("cameraTools").open=true;document.getElementById("startCamera").click();true');
  await new Promise(r=>setTimeout(r,1200));
  const after=await evaluate('fetch(document.body.dataset.base+"/api/camera/compatibility").then(r=>r.json())');
  const ui=await evaluate('({placeholder:document.getElementById("cameraPlaceholder").textContent,meta:document.getElementById("cameraMeta").textContent,buttonDisabled:document.getElementById("startCamera").disabled})');
  assert.equal(after.stage,'NOT_ENUMERATED');assert.equal(ui.buttonDisabled,false);
  assert.match(ui.placeholder,/手机系统未枚举到USB相机/);
  assert.equal(requests.filter(p=>p==='camera/start').length,1);
  assert.equal(requests.filter(p=>p.startsWith('drive/')||p.startsWith('gimbal/')).length,0);
  const state=await evaluate('fetch(document.body.dataset.base+"/api/status").then(r=>r.json()).then(d=>({drive_active:d.drive.active,control_active:d.control.active,camera_running:d.camera.running}))');
  assert.equal(state.drive_active,false);assert.equal(state.control_active,false);assert.equal(state.camera_running,false);
  const report={scope:'ACTUAL_PHONE_WEBVIEW_66; no attached USB camera',old_module_rejected:syntax.oldError,new_module_parsed:syntax.newError==='',imu_host_parity_cases:fixtures.length,ready,after_stage:after.stage,ui,state,camera_start_requests:requests.filter(p=>p==='camera/start').length,actuator_requests:requests.filter(p=>p.startsWith('drive/')||p.startsWith('gimbal/')).length,uncaught_js_exceptions:events,live_camera_acceptance:false};
  fs.writeFileSync(path.join(out,'phone-webview-check.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{ws.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
