import {$,all,text,badge,clamp} from '../core/dom.js';
import {protectHoldControl} from '../core/control-touch.js';
/** Owns the control lease, pointer/keyboard input and stale-command cancellation. */
export function createGimbal(api) {
  let session=null, epoch=0, pending=false, sendPending=false, heartbeatPending=false;
  let dirty=false,yaw=0,pitch=0,amplitude=100,pointer=null,latest=null,lastStatus=0;
  let calibration=null,calibrationPending=false,speedDirty=false,followPreparing=false;
  const pitchLabel=value=>value<0?value+' · 抬头':value>0?'+'+value+' · 低头':'0 · 中位';
  function relative(value,axis){if(!calibration)return Math.round((value-1500)/5);const c=calibration[axis+'_center'],edge=calibration[axis+(value<c?'_min':'_max')];return Math.round((value-c)*100/Math.abs(edge-c));}
  function profile(value){
    if(!value)return;calibration=value;
    if(!speedDirty)$('gimbalSpeed').value=String(value.rate);
    text('gimbalProfileValues','水平 '+value.yaw_min+' / '+value.yaw_center+' / '+value.yaw_max+'；俯仰 '+value.pitch_min+' / '+value.pitch_center+' / '+value.pitch_max+'（控制值）');
    text('gimbalCenterSaved',value.confirm_center?'已保存电子中位；实际对正仍由你目视确认。':'中位尚未校准。手动掰动后的角度无法自动读取。');
  }
  const nudge=all('[data-axis]');
  protectHoldControl($('joystick'));nudge.forEach(protectHoldControl);
  function axes(active) {
    active=Boolean(active&&!calibrationPending&&!followPreparing);
    ['yaw','pitch','centerControl'].forEach(id=>$(id).disabled=!active);
    nudge.forEach(node=>node.disabled=!active);
    all('[data-gimbal-calibrate]').forEach(node=>node.disabled=!(active&&calibration&&!calibrationPending&&!dirty&&!sendPending));
    if($('gimbalSaveSpeed'))$('gimbalSaveSpeed').disabled=Boolean(session||latest&&latest.control&&latest.control.active||calibrationPending);
    if($('gimbalResetBounds'))$('gimbalResetBounds').disabled=$('gimbalSaveSpeed').disabled;
    $('joystick').setAttribute('aria-disabled',String(!active));
    if(!active){pointer=null;text('stickNote','等待开启控制');}
  }
  function paint() {
    ['yaw','pitch'].forEach(id=>{$(id).min=-amplitude;$(id).max=amplitude;});
    all('[data-limit-low]').forEach(n=>n.textContent='−'+amplitude);all('[data-limit-high]').forEach(n=>n.textContent='+'+amplitude);
    $('yaw').value=yaw;$('pitch').value=pitch;text('yawValue',yaw);text('pitchValue',pitchLabel(pitch));
    $('stickThumb').style.left=(50+yaw/amplitude*38)+'%';$('stickThumb').style.top=(50+pitch/amplitude*38)+'%';
  }
  function mirrorFeedback(g) {
    if(!g||!g.active||!Number.isFinite(g.yaw_us)||!Number.isFinite(g.pitch_us)||g.yaw_us<500||g.yaw_us>2500||g.pitch_us<500||g.pitch_us>2500)return false;
    yaw=relative(g.yaw_us,'yaw');pitch=relative(g.pitch_us,'pitch');
    const extent=Math.max(amplitude,Math.abs(yaw),Math.abs(pitch));
    ['yaw','pitch'].forEach(id=>{$(id).min=-extent;$(id).max=extent;});
    all('[data-limit-low]').forEach(n=>n.textContent='−'+extent);all('[data-limit-high]').forEach(n=>n.textContent='+'+extent);
    $('yaw').value=yaw;$('pitch').value=pitch;text('yawValue',yaw);text('pitchValue',pitchLabel(pitch));
    $('stickThumb').style.left=(50+yaw/extent*38)+'%';$('stickThumb').style.top=(50+pitch/extent*38)+'%';
    return true;
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
    if(c.calibration)profile(c.calibration);
    const supported=!(data.capabilities&&data.capabilities.gimbal_control===false);
    all('[data-stop]').forEach(button=>button.disabled=!(supported||data.capabilities&&data.capabilities.drive_control));
    const online=Boolean(supported&&data.connected&&data.link_age_ms!=null&&data.link_age_ms<3000&&g&&g.ready);
    if(!pending&&session&&(!online||!c.active))localStop('控制已撤销，恢复连接后需要重新开启。');
    const active=Boolean(session&&online&&c.active);
    if(!session&&online)mirrorFeedback(g);
    axes(active);$('startControl').disabled=!online||(c.active&&c.state!=='AUTO_TRACKING')||pending||calibrationPending||data.diagnostics&&data.diagnostics.ok===false;
    $('startControl').textContent=c.state==='AUTO_TRACKING'?'切回手动控制':'开启云台控制';
    $('amplitude').disabled=Boolean(!session&&c.active);
    if(!session&&online&&c.active)text('stickNote','只读同步主控输出');
    badge('gimbalState',!supported?'遥控待接入':!online?'主控未就绪':active?'手动控制中':c.state==='AUTO_TRACKING'?'自动跟随中':c.active?'其他页面控制中':'已停止',active?'online':!online?'bad':'');
    if(!pending){
      if(!supported)text('gimbalFeedback',data.capabilities.gimbal_reason||'当前主控通信通道未开放云台控制。');
      else if(!online)text('gimbalFeedback','等待主控新鲜回执；不会自动恢复控制。');
      else if(active)text('gimbalFeedback','当前输出控制值：水平 '+g.yaw_us+' · 俯仰 '+g.pitch_us+'；等待停稳后可保存校准点。');
      else if(c.active)text('gimbalFeedback',g.active?'另一页面正在控制；此处同步CH32输出：水平 '+Math.round((g.yaw_us-1500)/5)+' · 俯仰 '+Math.round((g.pitch_us-1500)/5)+'。需要切换控制时，先停止云台，再在此开启。':'另一页面正在控制，等待CH32新的输出反馈。');
      else if(!c.active)text('gimbalFeedback','当前已停止输出。开启后才接受位置调整。');
    }
    const events=c.events||[];text('controlEvent',events.length?events[events.length-1].message:'');
  }
  async function acquireManual(e){
    const d=await api.post('gimbal/start');if(e!==epoch||document.hidden){if(d.session)await api.post('gimbal/stop',{session:d.session});throw Error('页面已离开，开启已撤销');}
    if(!d.session)throw Error('缺少控制会话回执');session=d.session;if(d.calibration)profile(d.calibration);
    yaw=pitch=0;paint();axes(true);text('gimbalFeedback','主控已接受开启，正在移向已设中位。');
  }
  $('startControl').addEventListener('click',async()=>{
    if(pending||!latest||!latest.connected||performance.now()-lastStatus>3000)return;
    pending=true;const e=++epoch;$('startControl').disabled=true;
    try{await acquireManual(e);}
    catch(error){if(e===epoch){if(session)await stop();else localStop('开启未确认');text('gimbalFeedback','开启未确认：'+error.message);}}
    finally{pending=false;}
  });
  all('[data-stop]').forEach(node=>node.addEventListener('click',stop));
  $('centerControl').addEventListener('click',async()=>{if(!session)return;const e=epoch;dirty=false;yaw=pitch=0;paint();try{await api.post('gimbal/center',{session});if(e===epoch)text('gimbalFeedback','回中指令已由主控接收。');}catch(error){if(e===epoch)await stop();}});
  function target(y,p){if(!session)return;yaw=clamp(y,amplitude);pitch=clamp(p,amplitude);paint();dirty=true;}
  $('yaw').addEventListener('input',()=>target($('yaw').value,pitch));
  $('pitch').addEventListener('input',()=>target(yaw,$('pitch').value));
  nudge.forEach(button=>button.addEventListener('click',()=>{const step=Math.sign(Number(button.dataset.step))*Number($('gimbalStep').value);target(yaw+(button.dataset.axis==='yaw'?step:0),pitch+(button.dataset.axis==='pitch'?step:0));}));
  $('gimbalSpeed').addEventListener('change',()=>{speedDirty=true;});
  $('gimbalSaveSpeed').addEventListener('click',async()=>{
    if(session||calibrationPending)return;calibrationPending=true;axes(false);const e=++epoch;
    try{const value=await api.post('gimbal/settings',{rate:Number($('gimbalSpeed').value)});if(e!==epoch)return;speedDirty=false;profile(value);text('gimbalCalibrationStatus','速度已保存在小手机，重新开启云台后使用。');}
    catch(error){text('gimbalCalibrationStatus','保存未完成：'+error.message);}finally{calibrationPending=false;}
  });
  $('gimbalResetBounds').addEventListener('click',async()=>{
    if(session||calibrationPending)return;calibrationPending=true;axes(false);const e=++epoch;
    try{const value=await api.post('gimbal/settings',{yaw_min:500,yaw_max:2500,pitch_min:500,pitch_max:2500});if(e!==epoch)return;profile(value);text('gimbalCalibrationStatus','已恢复完整软件范围；没有执行扫边或移动。中位保留。');}
    catch(error){text('gimbalCalibrationStatus','恢复未完成：'+error.message);}finally{calibrationPending=false;}
  });
  all('[data-gimbal-calibrate]').forEach(button=>button.addEventListener('click',async()=>{
    if(!session||dirty||sendPending||calibrationPending)return;calibrationPending=true;axes(false);const e=++epoch;
    try{const value=await api.post('gimbal/calibrate',{session,point:button.dataset.gimbalCalibrate});if(e!==epoch||document.hidden||!session)return;profile(value.calibration);yaw=value.target.yaw;pitch=value.target.pitch;paint();text('gimbalCalibrationStatus','校准点已保存在小手机。保存本身不移动云台。');}
    catch(error){if(e===epoch)text('gimbalCalibrationStatus','校准未保存：'+error.message);}finally{calibrationPending=false;}
  }));
  $('amplitude').addEventListener('change',()=>{amplitude=Number($('amplitude').value);['yaw','pitch'].forEach(id=>{$(id).min=-amplitude;$(id).max=amplitude;});all('[data-limit-low]').forEach(n=>n.textContent='−'+amplitude);all('[data-limit-high]').forEach(n=>n.textContent='+'+amplitude);yaw=clamp(yaw,amplitude);pitch=clamp(pitch,amplitude);paint();if(session)dirty=true;});
  function move(e){if(!session||$('joystick').getAttribute('aria-disabled')==='true')return;const r=$('joystick').getBoundingClientRect();target((e.clientX-r.left-r.width/2)/(r.width*.38)*amplitude,(e.clientY-r.top-r.height/2)/(r.height*.38)*amplitude);text('stickNote','正在调整两轴');}
  $('joystick').addEventListener('pointerdown',e=>{if(!session)return;e.preventDefault();pointer=e.pointerId;$('joystick').setPointerCapture(pointer);move(e);});
  $('joystick').addEventListener('pointermove',e=>{if(e.pointerId===pointer)move(e);});
  function release(e){if(e.pointerId===pointer){pointer=null;text('stickNote','已松手，保持当前位置');}}
  ['pointerup','pointercancel','lostpointercapture'].forEach(name=>$('joystick').addEventListener(name,release));
  $('joystick').addEventListener('keydown',e=>{const d={ArrowLeft:[-5,0],ArrowRight:[5,0],ArrowUp:[0,-5],ArrowDown:[0,5]}[e.key];if(!session||!d)return;e.preventDefault();target(yaw+d[0],pitch+d[1]);});
  const targetPeriod=50;
  const targetTimer=setInterval(async()=>{if(!session||!dirty||sendPending||document.hidden)return;const e=epoch;const payload={session,yaw,pitch};sendPending=true;dirty=false;try{await api.post('gimbal/set',payload);}catch(error){if(e===epoch)await stop();}finally{sendPending=false;}},targetPeriod);
  const heartbeatTimer=setInterval(async()=>{if(!session||heartbeatPending||document.hidden)return;if(performance.now()-lastStatus>3000){await stop();return;}heartbeatPending=true;const e=epoch;try{await api.post('gimbal/heartbeat',{session});}catch(error){if(e===epoch)await stop();}finally{heartbeatPending=false;}},400);
  function leave(){if(!session&&!pending)return;const token=session;localStop('页面已进入后台，已请求停止。');if(token)api.beacon('gimbal/stop',{session:token});}
  paint();axes(false);
  async function startSettings(info){$('gimbalCalibration').hidden=!info.gimbal_calibration;if(!info.gimbal_calibration)return;try{profile(await api.get('gimbal/settings'));}catch(error){text('gimbalCalibrationStatus','参数暂不可读：'+error.message);}}
  function canHandOff(){return Boolean(session&&!pending&&!dirty&&!sendPending&&!calibrationPending);}
  function handOff(){if(!canHandOff())throw Error('请先在本页手动对准目标，等云台停稳后交接。');const offered=session;localStop('正在将当前位置交给自动跟随…');return {session:offered,epoch};}
  function followReadiness(){
    if(pending||dirty||sendPending||calibrationPending)return {ready:false,message:'等待云台指令完成。'};
    if(canHandOff())return {ready:true,fromCenter:false,message:'将保持当前对准位置，交给自动跟随。'};
    const c=latest&&latest.control,g=latest&&latest.gimbal;
    if(!latest||!latest.connected||!g||!g.ready||performance.now()-lastStatus>3000)return {ready:false,message:'请先连接主控并开始记录。'};
    if(c&&c.active)return {ready:false,message:'其他页面持有云台控制；请先停止后再在本页启动。'};
    if(!calibration||!calibration.confirm_center)return {ready:false,message:'先手动对准目标并保存中位，或在本页手动控制后交接。'};
    return {ready:true,fromCenter:true,message:'点击后从已保存中位开始，不需要先开手动控制。'};
  }
  function targetPulse(axis,value,p){
    const mid=p[axis+'_center'];return mid+Math.round(value*(value<0?mid-p[axis+'_min']:p[axis+'_max']-mid)/100);
  }
  async function prepareForFollow(){
    const ready=followReadiness();if(!ready.ready)throw Error(ready.message);
    pending=true;followPreparing=true;const e=++epoch;axes(false);$('startControl').disabled=true;
    try{
      if(!session)await acquireManual(e);
      const until=performance.now()+2600;
      while(performance.now()<until){
        if(e!==epoch||document.hidden)throw Error('准备已撤销');
        const d=await api.get('status',1800);
        if(e!==epoch||document.hidden)throw Error('准备已撤销');
        latest=d;lastStatus=performance.now();const g=d.gimbal,c=d.control;
        if(!d.connected||!c||!c.active||!g||!g.active)throw Error('主控控制已撤销，请重新启动');
        const t=c.target,p=c.calibration||calibration;
        if(t&&p&&Math.abs(g.yaw_us-targetPulse('yaw',t.yaw,p))<=2&&Math.abs(g.pitch_us-targetPulse('pitch',t.pitch,p))<=2){
          pending=false;followPreparing=false;return handOff();
        }
        await new Promise(resolve=>setTimeout(resolve,100));
      }
      throw Error('云台尚未停稳，准备超时；请对准后重试');
    }catch(error){if(e===epoch){const token=session;localStop('准备未完成：'+error.message);if(token)try{await api.post('gimbal/stop',{session:token});}catch(ignored){}}throw error;}
    finally{pending=false;followPreparing=false;axes(Boolean(session));}
  }
  async function recoverFromFollow(offered){if(epoch!==offered.epoch||session||pending||document.hidden)return;try{await api.post('gimbal/heartbeat',{session:offered.session});if(epoch===offered.epoch&&!document.hidden){session=offered.session;axes(true);text('gimbalFeedback','交接未完成，仍保留手动控制。');}}catch(error){if(epoch===offered.epoch)localStop('手动会话已撤销，请重新开启。');}}
  return {render,stop,leave,startSettings,canHandOff,handOff,followReadiness,prepareForFollow,recoverFromFollow,version:()=>epoch,destroy(){leave();clearInterval(targetTimer);clearInterval(heartbeatTimer);}};
}
