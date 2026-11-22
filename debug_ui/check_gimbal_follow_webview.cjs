/** Read the installed phone WebView through ADB-local CDP. No external browser. */
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const out=process.env.ZX_GIMBAL_CHECK_OUT||path.resolve(__dirname,'../../output/onboard_dashboard/gimbal-follow-20261107');
const expected=JSON.parse(fs.readFileSync(path.join(out,'build-result.json'),'utf8')).version;
(async()=>{
 const targets=JSON.parse(fs.readFileSync(path.join(out,'phone-cdp-targets-private.json'),'utf8'));
 const target=targets.find(t=>t.type==='page');assert(target);
 const ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise((ok,no)=>{ws.onopen=ok;ws.onerror=no;});
 let id=0;const pending=new Map(),errors=[],requests=[];
 ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.id&&pending.has(d.id)){const p=pending.get(d.id);pending.delete(d.id);clearTimeout(p.timer);d.error?p.no(Error(JSON.stringify(d.error))):p.ok(d.result);}else if(d.method==='Runtime.exceptionThrown')errors.push(d.params);else if(d.method==='Network.requestWillBeSent'&&d.params.request.url.includes('/api/'))requests.push(d.params.request.url.split('/api/')[1]);};
 const send=(method,params={})=>new Promise((ok,no)=>{const n=++id;pending.set(n,{ok,no,timer:setTimeout(()=>{pending.delete(n);no(Error(method+' timeout'));},15000)});ws.send(JSON.stringify({id:n,method,params}));});
 const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
 try{
  await send('Runtime.discardConsoleEntries');await send('Runtime.enable');await send('Network.enable');errors.length=0;
  const before=await evaluate('(async()=>{const get=p=>fetch(document.body.dataset.base+"/api/"+p).then(r=>r.json());return {info:await get("ui/info"),follow:await get("gimbal-follow/status"),state:await get("status")};})()');
  assert.equal(before.info.source_version,expected);assert.equal(before.info.gimbal_follow,true);
  assert.equal(before.follow.active,false);assert.equal(before.follow.available,false);
  await new Promise(r=>setTimeout(r,1200));
  const ui=await evaluate('({ready:document.documentElement.getAttribute("data-ui-ready"),panel:!!document.getElementById("gimbalFollowPanel"),panelHidden:document.getElementById("gimbalFollowPanel").hidden,startDisabled:document.getElementById("followStart").disabled,stopDisabled:document.getElementById("followStop").disabled,axes:document.getElementById("followAxes").value,amplitude:document.getElementById("amplitude").value,manualSpeed:document.getElementById("gimbalSpeed").value,modelPanel:!!document.getElementById("largeVisionPanel"),message:document.getElementById("followMessage").textContent,userAgent:navigator.userAgent})');
  if(expected==='0.28.1'){assert.equal(ui.amplitude,'100');assert.equal(ui.manualSpeed,'1000');}
  if(['0.28.2','0.28.3','0.28.4','0.28.5','0.28.6','0.28.7'].includes(expected)){assert.equal(ui.amplitude,'100');assert.equal(ui.manualSpeed,'4000');}
  let controlFixture=null;
  if(['0.28.2','0.28.3','0.28.4','0.28.5','0.28.6','0.28.7'].includes(expected)){
   const source=fs.readFileSync(path.join(__dirname,'checks/gimbal_controls_browser_fixture.js'),'utf8');
   const production=fs.readFileSync(path.join(__dirname,'assets/features/gimbal.js'),'utf8');
   controlFixture=await evaluate(source+';gimbalControlsBrowserFixture('+JSON.stringify(production)+')');
   assert.equal(controlFixture.up,-100);assert.equal(controlFixture.down,100);
   assert.equal(controlFixture.nudge,-1);assert.equal(controlFixture.key,-5);assert.equal(controlFixture.slider,100);
   assert.match(controlFixture.label,/低头/);
  }
  assert.equal(ui.ready,'true');assert.equal(ui.panel,true);assert.equal(ui.panelHidden,false);assert.equal(ui.startDisabled,true);assert.equal(ui.stopDisabled,true);assert.equal(ui.axes,expected==='0.28.0'||expected==='0.28.1'||expected==='0.28.2'?'yaw':'both');
  // The confirmation alone must never enable an unavailable controller.
  await evaluate('document.getElementById("followConfirmed").checked=true;document.getElementById("followConfirmed").dispatchEvent(new Event("change"));document.getElementById("followStart").click();true');
  await new Promise(r=>setTimeout(r,1000));
  assert.equal(await evaluate('document.getElementById("followStart").disabled'),true);
  await evaluate('document.getElementById("followConfirmed").checked=false;document.getElementById("followConfirmed").dispatchEvent(new Event("change"));true');
  const after=await evaluate('fetch(document.body.dataset.base+"/api/status").then(r=>r.json()).then(d=>({drive_active:d.drive.active,control_active:d.control.active}))');
  assert.equal(after.drive_active,false);assert.equal(after.control_active,false);
  assert.equal(requests.some(p=>/^(gimbal|gimbal-follow|drive)\/(start|set|heartbeat)/.test(p)),false);
  assert.equal(errors.length,0);
  const report={actual_phone_webview:true,external_browser_opened:false,version:before.info.source_version,ui,controlFixture,follow:before.follow,state:after,confirmation_cannot_bypass_readiness:true,actuator_start_or_set_requests:0,uncaught_js_exceptions:errors,physical_tracking_tested:false};
  fs.writeFileSync(path.join(out,'phone-webview-check.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{ws.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
