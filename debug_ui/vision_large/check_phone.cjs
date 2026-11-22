/** Real K99 WebView + real LAN model request using a labelled test picture. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../../..'),out=path.join(root,'output/onboard_dashboard/large-vision-20261107');
const runtime=JSON.parse(fs.readFileSync(path.join(out,'runtime.json'),'utf8'));
const endpoint=process.argv[2];if(!endpoint)throw Error('Pass the actual LAN bridge URL');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const child=require('node:child_process'),adb=path.join(root,'tmp/android-tools/platform-tools/adb.exe');
 const pid=child.execFileSync(adb,['shell','pidof','cn.zhixing.dashboard'],{encoding:'utf8',timeout:5000}).trim();assert.match(pid,/^[0-9]+$/);
 child.execFileSync(adb,['forward','tcp:18782','localabstract:webview_devtools_remote_'+pid],{timeout:5000});
 const targets=await fetch('http://127.0.0.1:18782/json/list').then(r=>r.json());
 assert.equal(targets.length,1);const ws=new WebSocket(targets[0].webSocketDebuggerUrl);
 let id=0;const pending=new Map(),exceptions=[],posts=[];
 ws.onmessage=event=>{const d=JSON.parse(event.data);if(d.id&&pending.has(d.id)){const p=pending.get(d.id);pending.delete(d.id);clearTimeout(p.timer);d.error?p.reject(Error(JSON.stringify(d.error))):p.resolve(d.result);}else if(d.method==='Runtime.exceptionThrown')exceptions.push(d.params);else if(d.method==='Network.requestWillBeSent'&&d.params.request.method==='POST')posts.push(d.params.request.url);};
 const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id,timer=setTimeout(()=>{pending.delete(n);reject(Error(method+' timeout'));},12000);pending.set(n,{resolve,reject,timer});ws.send(JSON.stringify({id:n,method,params}));});
 const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
 await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
 try{
  await send('Runtime.enable');await send('Network.enable');
  const info=await evaluate('fetch(document.body.dataset.base+"/api/ui/info").then(r=>r.json())');assert.equal(info.source_version,JSON.parse(fs.readFileSync(path.join(out,'build-result.json'),'utf8')).version);
  assert.equal(info.large_vision_settings,true);assert.equal(info.large_vision.url,endpoint);
  assert.equal(info.large_vision_relay,true);
  assert.equal(await evaluate('document.documentElement.getAttribute("data-ui-ready")'),'true');
  await evaluate('document.getElementById("vlmEndpoint").value='+JSON.stringify(endpoint)+';document.getElementById("vlmConnect").click();true');
  let connected=false;for(let n=0;n<80;n++){connected=await evaluate('document.getElementById("vlmState").textContent==="模型已连接"');if(connected)break;await pause(150);}
  if(!connected)throw Error(await evaluate('document.getElementById("vlmMessage").textContent'));
  // No camera is attached in this test. The UI must reject instead of reusing an old image.
  await evaluate('document.getElementById("vlmCapture").click();true');await pause(800);
  const missing=await evaluate('({message:document.getElementById("vlmMessage").textContent,answer:document.getElementById("vlmAnswer").textContent})');
  assert.match(missing.message,/没有新鲜相机画面/);assert.equal(missing.answer,'');
  // Controlled in-memory File tests the real WebView's FileReader/upload path.
  // It is explicitly synthetic and does not claim native picker/camera acceptance.
  const picture=fs.readFileSync(path.join(out,'events/20261107-025422-8c118d14.image')).toString('base64');
  await evaluate('(()=>{var raw=atob('+JSON.stringify(picture)+'),bytes=new Uint8Array(raw.length);for(var n=0;n<raw.length;n++)bytes[n]=raw.charCodeAt(n);var transfer=new DataTransfer();transfer.items.add(new File([bytes],"SYNTHETIC-TEST-NOT-CAMERA.jpg",{type:"image/jpeg"}));document.getElementById("vlmFile").files=transfer.files;return true;})()');
  await evaluate('document.getElementById("vlmAnalyzeFile").click();true');
  let done=false;for(let n=0;n<200;n++){const s=await evaluate('document.getElementById("vlmState").textContent');if(s==='本次识别完成'){done=true;break;}if(s==='本次未完成')throw Error(await evaluate('document.getElementById("vlmMessage").textContent'));await pause(500);}
  assert.equal(done,true);
  const ui=await evaluate('({answer:document.getElementById("vlmAnswer").textContent,metrics:document.getElementById("vlmMetrics").textContent,source:document.getElementById("vlmProvenance").textContent,viewport:innerWidth,overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth,ua:navigator.userAgent})');
  assert.match(ui.metrics,/qwen3-vl:8b-instruct/);assert.match(ui.source,/手动选中照片/);assert.equal(ui.overflow,false);assert.equal(exceptions.length,0);
  assert.equal(posts.filter(p=>/\/api\/(drive|gimbal)\//.test(p)).length,0);
  assert.ok(posts.some(p=>new URL(p).hostname==='127.0.0.1'&&p.includes('/api/vlm/analyze')),'Image/model requests must use phone same-origin relay');
  // This old WebView does not reliably implement CDP Page.captureScreenshot.
  const shot=require('node:child_process').execFileSync(path.join(root,'tmp/android-tools/platform-tools/adb.exe'),['exec-out','screencap','-p'],{timeout:10000});
  fs.writeFileSync(path.join(out,'actual-phone-large-vision.png'),shot);
  const report={actual_phone_webview:true,version:info.source_version,same_origin_phone_relay:true,model_reached_over_lan:true,endpoint_host:new URL(endpoint).hostname,selected_image_is_synthetic_fixture:true,live_camera_acceptance:false,missing_camera_rejected:missing,ui,exceptions,actuator_posts:0};
  fs.writeFileSync(path.join(out,'actual-phone-large-vision.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{ws.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
