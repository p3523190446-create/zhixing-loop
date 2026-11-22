import {$,all,text,badge,clamp} from '../core/dom.js';
/** Owns the control lease, pointer/keyboard input and stale-command cancellation. */
export function createGimbal(api) {
  let session=null, epoch=0, pending=false, sendPending=false, heartbeatPending=false;
  let dirty=false,yaw=0,pitch=0,amplitude=60,pointer=null,latest=null,lastStatus=0;
  const nudge=all('[data-axis]');
  function axes(active) {
    ['yaw','pitch','centerControl'].forEach(id=>$(id).disabled=!active);
    nudge.forEach(node=>node.disabled=!active);
    $('joystick').setAttribute('aria-disabled',String(!active));
    if(!active){pointer=null;text('stickNote','等待开启控制');}
  }
  function paint() {
    $('yaw').value=yaw;$('pitch').value=pitch;text('yawValue',yaw);text('pitchValue',pitch);
    $('stickThumb').style.left=(50+yaw/amplitude*38)+'%';$('stickThumb').style.top=(50+pitch/amplitude*38)+'%';
  }
  function localStop(message) {epoch++;session=null;dirty=false;axes(false);text('gimbalFeedback',message);}
  async function stop() {
    localStop('正在等待主控停止回执…');
    try {const d=await api.post('gimbal/stop');if(!d.stopped)throw Error('主控未确认停止');text('gimbalFeedback','主控已确认停止输出。');}
    catch(e){text('gimbalFeedback','停止回执未确认：'+e.message+'。不要把按钮状态当作实物已停。');}
  }
  function render(data, requestEpoch=epoch) {
    if(requestEpoch!==epoch)return;
    latest=data;lastStatus=performance.now();const g=data.gimbal,c=data.control||{};
    const online=Boolean(data.connected&&data.link_age_ms!=null&&data.link_age_ms<3000&&g&&g.ready&&(!data.capabilities||data.capabilities.gimbal!==false));
    if(!pending&&session&&(!online||!c.active))localStop('控制已撤销，恢复连接后需要重新开启。');
    const active=Boolean(session&&online&&c.active);
    axes(active);$('startControl').disabled=!online||c.active||pending||data.diagnostics&&data.diagnostics.ok===false;
    badge('gimbalState',!online?'主控未就绪':active?'手动控制中':c.active?'其他页面控制中':'已停止',active?'online':!online?'bad':'');
    if(!pending){
      if(data.capabilities&&data.capabilities.gimbal===false)text('gimbalFeedback','云台控制尚未接入车载网页，当前不会发送动作。');else if(!online)text('gimbalFeedback','等待主控新鲜回执；不会自动恢复控制。');
      else if(active)text('gimbalFeedback','主控输出指令：水平 '+Math.round((g.yaw_us-1500)/5)+' · 俯仰 '+Math.round((g.pitch_us-1500)/5)+'。');
      else if(!c.active)text('gimbalFeedback','当前已停止输出。开启后才接受位置调整。');
    }
    const events=c.events||[];text('controlEvent',events.length?events[events.length-1].message:'');
  }
  $('startControl').addEventListener('click',async()=>{
    if(pending||!latest||!latest.connected||performance.now()-lastStatus>3000)return;
    pending=true;const e=++epoch;$('startControl').disabled=true;
    try{const d=await api.post('gimbal/start');if(e!==epoch||document.hidden){await api.post('gimbal/stop');return;}if(!d.session)throw Error('缺少控制会话回执');session=d.session;yaw=pitch=0;paint();axes(true);text('gimbalFeedback','主控已接受开启，等待输出反馈。');}
    catch(error){await stop();text('gimbalFeedback','开启未确认：'+error.message);}
    finally{pending=false;}
  });
  all('[data-stop]').forEach(node=>node.addEventListener('click',stop));
  $('centerControl').addEventListener('click',async()=>{if(!session)return;const e=epoch;dirty=false;yaw=pitch=0;paint();try{await api.post('gimbal/center',{session});if(e===epoch)text('gimbalFeedback','回中指令已由主控接收。');}catch(error){if(e===epoch)await stop();}});
  function target(y,p){if(!session)return;yaw=clamp(y,amplitude);pitch=clamp(p,amplitude);paint();dirty=true;}
  $('yaw').addEventListener('input',()=>target($('yaw').value,pitch));
  $('pitch').addEventListener('input',()=>target(yaw,$('pitch').value));
  nudge.forEach(button=>button.addEventListener('click',()=>target(yaw+(button.dataset.axis==='yaw'?Number(button.dataset.step):0),pitch+(button.dataset.axis==='pitch'?Number(button.dataset.step):0))));
  $('amplitude').addEventListener('change',()=>{amplitude=Number($('amplitude').value);['yaw','pitch'].forEach(id=>{$(id).min=-amplitude;$(id).max=amplitude;});all('[data-limit-low]').forEach(n=>n.textContent='−'+amplitude);all('[data-limit-high]').forEach(n=>n.textContent='+'+amplitude);yaw=clamp(yaw,amplitude);pitch=clamp(pitch,amplitude);paint();if(session)dirty=true;});
  function move(e){if(!session||$('joystick').getAttribute('aria-disabled')==='true')return;const r=$('joystick').getBoundingClientRect();target((e.clientX-r.left-r.width/2)/(r.width*.38)*amplitude,(e.clientY-r.top-r.height/2)/(r.height*.38)*amplitude);text('stickNote','正在调整两轴');}
  $('joystick').addEventListener('pointerdown',e=>{if(!session)return;e.preventDefault();pointer=e.pointerId;$('joystick').setPointerCapture(pointer);move(e);});
  $('joystick').addEventListener('pointermove',e=>{if(e.pointerId===pointer)move(e);});
  function release(e){if(e.pointerId===pointer){pointer=null;text('stickNote','已松手，保持当前位置');}}
  ['pointerup','pointercancel','lostpointercapture'].forEach(name=>$('joystick').addEventListener(name,release));
  $('joystick').addEventListener('keydown',e=>{const d={ArrowLeft:[-5,0],ArrowRight:[5,0],ArrowUp:[0,-5],ArrowDown:[0,5]}[e.key];if(!session||!d)return;e.preventDefault();target(yaw+d[0],pitch+d[1]);});
  const targetTimer=setInterval(async()=>{if(!session||!dirty||sendPending||document.hidden)return;const e=epoch;const payload={session,yaw,pitch};sendPending=true;dirty=false;try{await api.post('gimbal/set',payload);}catch(error){if(e===epoch)await stop();}finally{sendPending=false;}},200);
  const heartbeatTimer=setInterval(async()=>{if(!session||heartbeatPending||document.hidden)return;if(performance.now()-lastStatus>3000){await stop();return;}heartbeatPending=true;const e=epoch;try{await api.post('gimbal/heartbeat',{session});}catch(error){if(e===epoch)await stop();}finally{heartbeatPending=false;}},400);
  function leave(){if(!session&&!pending)return;localStop('页面已进入后台，已请求停止。');api.beacon('gimbal/stop');}
  paint();axes(false);
  return {render,stop,leave,version:()=>epoch,destroy(){leave();clearInterval(targetTimer);clearInterval(heartbeatTimer);}};
}
