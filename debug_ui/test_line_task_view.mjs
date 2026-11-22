import assert from 'node:assert/strict';
import {createLineTaskPlan} from './assets/features/line-task-plan.js';
class Element {constructor(value=''){this.value=value;this.disabled=false;this.events={};this.textContent='';}addEventListener(name,fn){this.events[name]=fn;}}
const ids=['lineTaskPlan','lineTaskBranch','lineTaskPace','lineTaskDuration','lineTaskSide','startLineTask','stopLineTask','lineTaskFeedback','lineTaskPlanSaved'];
const elements=Object.fromEntries(ids.map(id=>[id,new Element()]));elements.lineTaskBranch.value='stop';elements.lineTaskPace.value='40';elements.lineTaskDuration.value='5';
globalThis.document={hidden:false,getElementById:id=>elements[id],querySelectorAll:()=>[]};globalThis.localStorage={getItem:()=>null,setItem(){}};globalThis.addEventListener=()=>{};let tick;globalThis.setInterval=fn=>{tick=fn;};
let calls=[],resolveStart;const api={post:async(path,body)=>{calls.push({path,body});if(path==='line-task/start')return {session:'test'};if(path==='line-task/stop')return {stopped:true};return {ok:true};},beacon:path=>calls.push({path,beacon:true})};
const view=createLineTaskPlan(api);const fresh={connected:true,age_ms:10,line_task:{supported:false,available:false,message:'主控未部署自动循迹执行版'}};
view.render(fresh);assert.equal(elements.startLineTask.disabled,true);assert.match(elements.lineTaskFeedback.textContent,/未部署/);assert.equal(calls.length,0);
const ready={connected:true,age_ms:10,line_task:{supported:true,available:true,active:false,mcu_active:false}};
view.render(ready);assert.equal(elements.startLineTask.disabled,true);elements.lineTaskSide.value='1';elements.lineTaskSide.events.change();assert.equal(elements.startLineTask.disabled,false);
await elements.startLineTask.events.click();assert.deepEqual(calls[0],{path:'line-task/start',body:{branch:0,speed:40,duration_ms:5000,x1_left:1}});assert.equal(elements.startLineTask.disabled,true);
await tick();assert.equal(calls[1].path,'line-task/heartbeat');assert.equal(calls[1].body.session,'test');
view.render(fresh,0);assert.equal(calls.length,2); // A response requested before START cannot revoke the new owner.
await view.stop();assert.equal(calls[2].path,'line-task/stop');
view.render(ready);await elements.startLineTask.events.click();view.leave();assert.equal(calls.at(-1).path,'line-task/stop');assert.equal(calls.at(-1).beacon,true);
view.render({connected:false});assert.equal(elements.startLineTask.disabled,true);
api.post=(path,body)=>{calls.push({path,body});return path==='line-task/start'?new Promise(r=>{resolveStart=r;}):Promise.resolve({stopped:true});};view.render(ready);
const pending=elements.startLineTask.events.click();view.leave();resolveStart({session:'late'});await pending;assert.equal(calls.at(-1).path,'line-task/stop');
elements.lineTaskBranch.value='left';elements.lineTaskPace.value='60';elements.lineTaskDuration.value='10';
view.render({...ready,line_task:{...ready.line_task,trial:true}});
assert.equal(elements.lineTaskBranch.value,'stop');assert.equal(elements.lineTaskPace.value,'40');assert.equal(elements.lineTaskDuration.value,'5');
view.render({...ready,line_calibration:{ready:false,busy:false}});assert.equal(elements.startLineTask.disabled,true);
api.post=async(path,body)=>{calls.push({path,body});return path==='line-task/start'?{session:'loop'}:{stopped:true};};
view.render({...ready,line_task:{...ready.line_task,loop_supported:true},line_calibration:{ready:true,busy:false}});
assert.equal(elements.lineTaskBranch.value,'loop');assert.equal(elements.lineTaskDuration.value,'0');await elements.startLineTask.events.click();assert.deepEqual(calls.at(-1).body,{branch:4,speed:40,duration_ms:0,x1_left:1});
view.render({...ready,line_task:{...ready.line_task,loop_supported:true,active:true,mcu_active:true,state:3}});assert.match(elements.lineTaskFeedback.textContent,/找线/);await view.stop();
for(const [reason,label] of [[9,/电机反馈/],[10,/控制连接中断/]]){
  const fault={...ready,line_task:{...ready.line_task,state:5,reason}};
  view.render(fault);assert.match(elements.lineTaskFeedback.textContent,label);
  view.render(fault);assert.match(elements.lineTaskFeedback.textContent,label);
}
console.log('PASS line task view: gates, legacy trial, continuous ring branch4/duration0, recovery status, explicit start/heartbeat/stop, stale/late/disconnect');
