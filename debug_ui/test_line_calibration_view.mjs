import assert from 'node:assert/strict';
import {createLineCalibration} from './assets/features/line-calibration.js';
import {lineView} from './assets/features/line.js';
class Element{constructor(){this.disabled=false;this.hidden=false;this.events={};this.dataset={};this.classList={toggle(){}};}addEventListener(n,f){this.events[n]=f;}}
const ids=['lineCalibration','lineCalFloor','lineCalBlack','lineCalSave','lineCalMessage','lineCalBadge','lineCalProgress','lineCalCancel','lineCalFloorStep','lineCalBlackStep','lineCalSaveStep'];
const nodes=Object.fromEntries(ids.map(id=>[id,new Element()]));globalThis.document={getElementById:id=>nodes[id]};
let requests=[];const api={post:async(path)=>{requests.push(path);return {supported:true,busy:true,surface:'floor',message:'地砖采集中',remaining_ms:6000};}};
const view=createLineCalibration(api);view.start({line_calibration:true});assert.equal(nodes.lineCalibration.hidden,false);assert.equal(nodes.lineCalFloor.disabled,true);assert.equal(requests.length,0);
const render=(c,extra={})=>view.render({connected:true,age_ms:1,line_calibration:{supported:true,...c},...extra});
render({});assert.equal(nodes.lineCalFloor.disabled,false);assert.equal(nodes.lineCalBlack.disabled,true);assert.equal(nodes.lineCalSave.disabled,true);
await nodes.lineCalFloor.events.click();assert.deepEqual(requests,['line-calibration/floor']);assert.equal(nodes.lineCalFloor.disabled,true);assert.equal(nodes.lineCalProgress.hidden,false);
render({floor_done:true,busy:false});assert.equal(nodes.lineCalBlack.disabled,false);assert.equal(nodes.lineCalSave.disabled,true);
render({floor_done:true,black_done:true});assert.equal(nodes.lineCalSave.disabled,false);
render({ready:true,saved:true});assert.equal(nodes.lineCalBadge.textContent,'已应用');render({}, {connected:false});assert.equal(nodes.lineCalFloor.disabled,true);
const profile={floor:Array(8).fill(1200),black:Array(8).fill(3200)},raw=Array(8).fill(1200);raw[3]=raw[4]=3200;
const data={connected:true,line:{valid:true,age_ms:2,raw,digital_mask:0},line_calibration:{ready:true,profile}};
const result=lineView(data);assert.equal(result.count,2);assert.equal(result.state,'line');assert.ok(Math.abs(result.position)<1e-10);assert.equal(result.channels[0].strength,0);assert.equal(result.channels[3].strength,1);
data.line.raw=Array(8).fill(2199);assert.equal(lineView(data).count,0);data.line.raw=Array(8).fill(2200);assert.equal(lineView(data).count,8);
console.log('PASS calibration UI: offline/read-only, ordered actions, busy/save gates, applied state, same analog midpoint as MCU despite module digital mask');
