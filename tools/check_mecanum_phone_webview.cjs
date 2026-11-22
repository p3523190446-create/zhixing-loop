const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const out=process.env.ZX_CHECK_OUT||path.resolve(__dirname,'../../output/onboard_dashboard/mecanum-live-20261107');
(async()=>{
 const targets=JSON.parse(fs.readFileSync(path.join(out,'private-phone-cdp.json'),'utf8'));
 const target=targets.find(x=>x.type==='page');assert(target);
 const socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((ok,no)=>{socket.onopen=ok;socket.onerror=no;});
 let id=0;const pending=new Map();socket.onmessage=event=>{const d=JSON.parse(event.data);const p=pending.get(d.id);if(p){pending.delete(d.id);clearTimeout(p.timer);d.error?p.no(Error(JSON.stringify(d.error))):p.ok(d.result);}};
 const send=(method,params={})=>new Promise((ok,no)=>{const n=++id,timer=setTimeout(()=>no(Error('CDP timeout')),7000);pending.set(n,{ok,no,timer});socket.send(JSON.stringify({id:n,method,params}));});
 try{
  const r=await send('Runtime.evaluate',{expression:`(()=>({ready:document.documentElement.dataset.uiReady,driveModule:!!document.getElementById('driveInputHint'),rotationButtons:document.querySelectorAll('[data-mecanum-only] [data-drive-direction]').length,lineTask:!!document.getElementById('lineTaskPace'),camera:!!document.getElementById('startCamera'),stop:!!document.getElementById('stopDrive'),dualPads:!!document.getElementById('driveTurnPad'),pointerEvents:typeof PointerEvent==='function',pointerCapture:typeof document.getElementById('driveJoystick').setPointerCapture==='function',noHorizontalOverflow:document.documentElement.scrollWidth<=innerWidth,ua:navigator.userAgent}))()`,returnByValue:true});
  assert(!r.exceptionDetails);const view=r.result.value;fs.writeFileSync(path.join(out,'phone-webview-view.json'),JSON.stringify(view,null,2));assert.equal(view.ready,'true');assert.equal(view.rotationButtons,2);assert(view.driveModule&&view.lineTask&&view.camera&&view.stop&&view.dualPads&&view.pointerEvents&&view.pointerCapture&&view.noHorizontalOverflow);
  const report={result:'PASS',scope:'Actual connected phone WebView parses current modules; no P7/camera/ground acceptance',view,motion_requests:0};
  fs.writeFileSync(path.join(out,'phone-webview-check.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{socket.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
