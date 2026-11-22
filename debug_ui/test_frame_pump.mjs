import assert from 'node:assert/strict';
import {createFramePump} from './assets/features/frame-pump.js';

async function simulate(workMs,active=true){
  let now=0,index=0,inflight=0,maxInflight=0,calls=0,queue=[];
  const clock={now:()=>now,set:(callback,delay)=>{const task={id:++index,at:now+delay,callback};queue.push(task);return task.id;},clear:id=>{queue=queue.filter(task=>task.id!==id);}};
  const pump=createFramePump(async()=>{inflight++;maxInflight=Math.max(maxInflight,inflight);calls++;now+=workMs;inflight--;},()=>active,()=>1000/30,clock);
  while(queue.length){queue.sort((a,b)=>a.at-b.at);const task=queue.shift();if(task.at>10000)break;now=Math.max(now,task.at);await task.callback();assert.ok(queue.length<=1,'Requests/timers must not build a queue');}
  pump.close();return {calls,maxInflight};
}
const fast=await simulate(0),slow=await simulate(60),hidden=await simulate(0,false);
assert.ok(fast.calls>=299&&fast.calls<=302);assert.equal(fast.maxInflight,1);
assert.ok(slow.calls>=160&&slow.calls<=166);assert.equal(slow.maxInflight,1);
assert.equal(hidden.calls,0);
console.log(JSON.stringify({controlled_timers:true,fast,slow,hidden,physical_browser_fps_verified:false}));
