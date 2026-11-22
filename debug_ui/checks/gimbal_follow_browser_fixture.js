/* Production follow component on detached controls; all APIs and timers are fake. */
async function gimbalFollowBrowserFixture(source){
 const make=new Function('$','all','document','setInterval','clearInterval',source.replace(/^import .*;$/gm,'').replace('export function','function')+';return createGimbalFollow;');
 async function scenario(manual){
  const body=document.body.cloneNode(true);body.querySelectorAll('#gimbalFollowPanel').forEach(n=>n.remove());
  const $=id=>body.querySelector('#'+id),all=s=>Array.from(body.querySelectorAll(s)),timers=[];
  const doc={createElement:document.createElement.bind(document),hidden:false};
  let active=false,postPending=false,resolveStart,resolveOld;const calls=[];
  const state=()=>({active,available:true,target_locked:true,message:'ready',max_tracking_rate_us_s:600});
  const api={get:async()=>{if(postPending)return new Promise(ok=>{resolveOld=ok;});return state();},
   post:async(path,data)=>{calls.push({path,data});if(path==='gimbal-follow/start'){postPending=true;return new Promise(ok=>{resolveStart=()=>{active=true;postPending=false;ok({...state(),session:'fake-only'});};});}return {ok:true};},
   beacon:()=>{}};
  const offered={session:'fake-manual',epoch:1};
  const gimbal={canHandOff:()=>manual,followReadiness:()=>({ready:true,fromCenter:!manual,message:'ready'}),handOff:()=>offered,
   prepareForFollow:async()=>offered,recoverFromFollow:async()=>{},stop:async()=>{}};
  const view=make($,all,doc,(fn,ms)=>{timers.push({fn,ms});return timers.length;},()=>{})(api,gimbal);
  const flush=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
  try{
   view.start({gimbal_follow:true});await flush();$('followConfirmed').checked=true;$('followConfirmed').dispatchEvent(new Event('change'));
   const enabled=!$('followStart').disabled;
   if(!enabled)return {enabled,heartbeat:false};
   $('followStart').click();await flush();
   timers.find(x=>x.ms===300).fn();await flush();
   resolveStart();await flush();
   if(resolveOld){resolveOld({active:false,available:true,target_locked:true});await flush();}
   timers.find(x=>x.ms===400).fn();await flush();
   return {enabled,heartbeat:calls.some(x=>x.path==='gimbal-follow/heartbeat'),late_poll_during_start:Boolean(resolveOld),
    requires_confirmation:true,start_body:calls.find(x=>x.path==='gimbal-follow/start').data};
  }finally{view.destroy();}
 }
 return {manual:await scenario(true),savedCenter:await scenario(false),fake_api:true,actual_motion:false};
}
