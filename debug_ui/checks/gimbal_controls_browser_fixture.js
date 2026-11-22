/* Detached production controls with a fake API; never touches real control nodes. */
async function gimbalControlsBrowserFixture(source){
 const root=document.body.cloneNode(true),el=id=>root.querySelector('#'+id),all=s=>Array.from(root.querySelectorAll(s));
 const factory=new Function('$','all','text','badge','clamp','protectHoldControl',source.replace(/^import .*;$/gm,'').replace('export function','function')+';return createGimbal;');
 const create=factory(el,all,(id,value)=>{el(id).textContent=value;},(id,value)=>{el(id).textContent=value;},(v,a)=>Math.max(-a,Math.min(a,Number(v))),()=>{});
 const posts=[],profile={yaw_min:500,yaw_center:1500,yaw_max:2500,pitch_min:500,pitch_center:1500,pitch_max:2500,rate:4000,confirm_center:false};
 const api={post:async(path,body)=>{posts.push({path,body});return path==='gimbal/start'?{session:'fixture-only',calibration:profile}:path==='gimbal/stop'?{stopped:true}:{ok:true};},beacon:()=>{},get:async()=>profile};
 const g=create(api),wait=()=>new Promise(r=>setTimeout(r,120)),last=()=>posts.filter(p=>p.path==='gimbal/set').slice(-1)[0].body;
 try{
  g.render({connected:true,link_age_ms:0,gimbal:{ready:1,active:0,yaw_us:0,pitch_us:0},control:{active:false,calibration:profile},diagnostics:{ok:true}});
  el('startControl').click();await wait();
  const stick=el('joystick');stick.setPointerCapture=()=>{};stick.getBoundingClientRect=()=>({left:0,top:0,width:200,height:200});
  stick.dispatchEvent(new PointerEvent('pointerdown',{pointerId:1,clientX:100,clientY:24}));await wait();const up=last().pitch;
  stick.dispatchEvent(new PointerEvent('pointerup',{pointerId:1}));
  stick.dispatchEvent(new PointerEvent('pointerdown',{pointerId:2,clientX:100,clientY:176}));await wait();const down=last().pitch;
  stick.dispatchEvent(new PointerEvent('pointerup',{pointerId:2}));
  el('centerControl').click();await wait();root.querySelector('[data-axis="pitch"][data-step="-5"]').click();await wait();const nudge=last().pitch;
  el('centerControl').click();await wait();stick.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowUp'}));await wait();const key=last().pitch;
  el('pitch').value=100;el('pitch').dispatchEvent(new Event('input'));await wait();
  return {up,down,nudge,key,slider:last().pitch,label:el('pitchValue').textContent,fake_api:true,detached_controls:true};
 }finally{g.destroy();}
}
