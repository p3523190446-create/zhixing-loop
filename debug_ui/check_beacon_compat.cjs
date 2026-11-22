/** Production API with fake network, including the Chrome 66 synchronous throw. */
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'assets/core/api.js'),'utf8').replace('export function','function');
const make=new Function('document','location','navigator','Blob','fetch','AbortController','setTimeout','clearTimeout',source+';return createApi;');
(async()=>{
 let checks=0;
 for(const mode of ['accepted','full','throws','missing']){
  const sent=[],fallback=[];
  const navigator=mode==='missing'?{}:{sendBeacon:(url,body)=>{sent.push({url,body});if(mode==='throws')throw new Error('Chrome 66 restriction');return mode==='accepted';}};
  const api=make({body:{dataset:{base:'/paired'}}},{},navigator,Blob,(url,options)=>{fallback.push({url,options});return Promise.resolve({});},AbortController,setTimeout,clearTimeout)();
  for(const route of ['drive/stop','gimbal/stop','gimbal-follow/stop','line-task/stop','record/stop']){
   const result=api.beacon(route,{session:'stale-fixture-only'});assert.equal(result,mode==='accepted');checks++;
  }
  for(const item of sent){assert.equal(item.body.type,'text/plain;charset=utf-8');assert.deepEqual(JSON.parse(await item.body.text()),{session:'stale-fixture-only'});checks+=2;}
  assert.equal(fallback.length,mode==='accepted'?0:5);checks++;
  for(const item of fallback){assert.equal(item.options.keepalive,true);assert.equal(item.options.headers['Content-Type'],'application/json');checks+=2;}
  const count=sent.length+fallback.length;assert.equal(api.beacon('gimbal/start',{}),false);assert.equal(sent.length+fallback.length,count);checks+=2;
 }
 const report={checks,result:'PASS',fake_network:true,actuator_commands_sent:false};
 fs.writeFileSync(path.join(process.env.ZX_GIMBAL_CHECK_OUT,'beacon-compat-checks.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1;});
