const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const out=process.env.ZX_GIMBAL_CHECK_OUT;
(async()=>{
 const target=JSON.parse(fs.readFileSync(path.join(out,'phone-cdp-targets-private.json'),'utf8'))[0];
 const ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise((ok,no)=>{ws.onopen=ok;ws.onerror=no;});
 let id=0;const pending=new Map();
 ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.id&&pending.has(d.id)){const p=pending.get(d.id);pending.delete(d.id);clearTimeout(p.t);d.error?p.no(Error(JSON.stringify(d.error))):p.ok(d.result);}};
 const send=(method,params)=>new Promise((ok,no)=>{const n=++id,t=setTimeout(()=>no(Error('CDP timeout')),8000);pending.set(n,{ok,no,t});ws.send(JSON.stringify({id:n,method,params}));});
 try{
  const fixture=fs.readFileSync(path.join(__dirname,'checks/gimbal_follow_browser_fixture.js'),'utf8');
  const source=fs.readFileSync(path.join(__dirname,'assets/features/gimbal-follow.js'),'utf8');
  const r=await send('Runtime.evaluate',{expression:fixture+';gimbalFollowBrowserFixture('+JSON.stringify(source)+')',returnByValue:true,awaitPromise:true});
  if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));
  const result=r.result.value;fs.writeFileSync(path.join(out,'follow-browser-fixture.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  if(!process.env.ZX_EXPECT_OLD_FAILURE){assert(result.manual.heartbeat);assert(result.savedCenter.enabled);assert(result.savedCenter.heartbeat);}
 }finally{ws.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
