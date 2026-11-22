async function gimbalPrepareBrowserFixture(source){
 const create=new Function('$','all','text','badge','clamp','protectHoldControl','performance','setInterval','clearInterval','setTimeout',
   source.replace(/^import .*;$/gm,'').replace('export function','function')+';return createGimbal;');
 async function scenario(kind){
  const body=document.body.cloneNode(true),$=id=>body.querySelector('#'+id),calls=[];let active=false,clock=10;
  const p={yaw_min:500,yaw_center:1490,yaw_max:2500,pitch_min:500,pitch_center:1480,pitch_max:2500,rate:4000,confirm_center:kind!=='uncalibrated'};
  const state=()=>({connected:true,link_age_ms:0,gimbal:{ready:1,active:active?1:0,yaw_us:kind==='unsettled'?1800:1490,pitch_us:1480},
   control:{active,target:{yaw:0,pitch:0},calibration:p},diagnostics:{ok:true}});
  const api={get:async()=>{clock+=200;return state();},post:async(path,b)=>{
   calls.push(path);if(path==='gimbal/start'){if(kind==='busy')throw Error('另一页面持有控制');active=true;return {session:'fake-only',calibration:p};}
   if(path==='gimbal/stop'){active=false;return {stopped:true};}return {ok:true};},beacon:()=>{}};
  const g=create($,s=>Array.from(body.querySelectorAll(s)),(id,v)=>{$(id).textContent=v;},(id,v)=>{$(id).textContent=v;},
   (v,a)=>Math.max(-a,Math.min(a,Number(v))),()=>{},{now:()=>clock},()=>1,()=>{},fn=>{fn();})(api);
  try{
   g.render(state());if(kind==='manual'){$('startControl').click();for(let i=0;i<10;i++)await Promise.resolve();}
   const ready=g.followReadiness();let offered,error;
   if(ready.ready)try{offered=await g.prepareForFollow();}catch(e){error=e.message;}
   return {kind,ready:ready.ready,offered:!!offered,error:error||null,start_count:calls.filter(p=>p==='gimbal/start').length,
    stop_count:calls.filter(p=>p==='gimbal/stop').length,profile_unchanged:p.yaw_center===1490&&p.pitch_center===1480};
  }finally{g.destroy();}
 }
 const result=[];for(const k of ['saved','manual','uncalibrated','unsettled','busy'])result.push(await scenario(k));return result;
}
