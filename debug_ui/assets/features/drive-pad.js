import {$,all,text,badge,clamp} from '../core/dom.js';
import {protectHoldControl} from '../core/control-touch.js';
import {createDriveResponse} from './drive-response.js';

/** Independent hold-to-run translation/rotation; the MCU owns final permission. */
export function createDrive(api) {
  let session=null,epoch=0,busy=false,sending=false,sequence=0,lastStatus=0,lastSent=0;
  let mecanum=true,available=false,braking=false,lastBrakeSeq=0,pendingZero=false;
  let movePointer=null,spinPointer=null,moveValue=[0,0],spinValue=0;
  let throttle=0,strafe=0,turn=0,holding=false;
  const keys=new Set(),pad=$('driveJoystick'),spinPad=$('driveTurnPad');
  const response=createDriveResponse(),softControl=$('driveSoft');let lastMessage='';
  const soft=()=>Boolean(softControl&&softControl.checked);
  const dead=value=>Math.abs(value)<8?0:clamp(Math.round(value),100);
  const key=value=>keys.has(value);
  function description(){
    if(!session)return '先开启遥控，再按住摇杆';
    if(!throttle&&!strafe&&!turn)return '摇杆已回中 · 当前零指令';
    const f=throttle>0?'前':throttle<0?'后':'',s=strafe>0?'右':strafe<0?'左':'';
    return [(throttle||strafe)?(mecanum?s+f+'平移':throttle>0?'前进':throttle<0?'后退':''):'',turn?(turn>0?'右转':'左转'):''].filter(Boolean).join(' + ');
  }
  function paint(){
    $('driveThumb').style.left=(50+(mecanum?strafe:turn)*.32)+'%';$('driveThumb').style.top=(50-throttle*.32)+'%';
    $('driveTurnThumb').style.left=(50+turn*.32)+'%';text('driveIntent',description());
    text('driveTarget',mecanum?`平移 前后 ${throttle} / 左右 ${strafe} · 转向 ${turn}`:`前后 ${throttle} / 转向 ${turn}`);
    pad.setAttribute('aria-disabled',String(!session));spinPad.setAttribute('aria-disabled',String(!session||!mecanum));
    $('startDrive').disabled=busy||Boolean(session)||!available;$('driveBrake').disabled=!session;
    all('[data-drive-direction]').forEach(b=>b.disabled=!session);text('drivePermission',session?'已开启遥控':'未开启');
    $('driveMotionDot').className=holding&&(throttle||strafe||turn)?'motion-dot active':'motion-dot';
  }
  function resetInput(){movePointer=spinPointer=null;moveValue=[0,0];spinValue=0;keys.clear();throttle=strafe=turn=0;holding=false;response.reset(performance.now());paint();}
  function input(){
    const f=movePointer!==null?moveValue[0]:(key('ArrowUp')||key('w')?100:0)-(key('ArrowDown')||key('s')?100:0);
    const side=movePointer!==null?moveValue[1]:(key('ArrowRight')||key('d')?100:0)-(key('ArrowLeft')||key('a')?100:0);
    throttle=dead(f);strafe=mecanum?dead(side):0;
    turn=mecanum?dead(spinPointer!==null?spinValue:(key('e')?100:0)-(key('q')?100:0)):dead(side);
    holding=movePointer!==null||spinPointer!==null||keys.size>0;paint();
  }
  function speedHint(){text('driveLimitValue',$('driveLimit').value+'%');text('driveSpeedHint',(soft()?'平稳操控：最高30%，缓起步、转向减敏。':'直接操控：按输入直接响应。')+'当前 '+$('driveLimit').value+'%；百分比不代表实测车速。');}
  function feedback(data={}){
    if(data.connected){const next=data.drive&&data.drive.chassis==='mecanum'||Boolean(data.capabilities&&data.capabilities.mecanum_control);if(next!==mecanum&&session)leave();mecanum=next;}
    text('driveTitle',mecanum?'麦轮遥控':'四驱遥控');text('driveMoveTitle',mecanum?'平移':'行驶');
    text('driveWestLabel',mecanum?'左移':'左转');text('driveEastLabel',mecanum?'右移':'右转');
    text('driveMoveHint',mecanum?'车头不转，朝推杆方向移动':'上下前后，左右转向');
    text('driveInputHint',mecanum?'左边平移，右边转向；可双指同时操作。全部松开，四轮归零。':'按住行驶，松手归零。');
    all('[data-mecanum-only]').forEach(el=>el.hidden=!mecanum);$('drivePlanes').classList.toggle('ordinary',!mecanum);
    const labels=mecanum?{left:'左移',right:'右移',forwardLeft:'左前',forwardRight:'右前',backLeft:'左后',backRight:'右后'}:{left:'左转',right:'右转',forwardLeft:'前进左拐',forwardRight:'前进右拐',backLeft:'倒车左转',backRight:'倒车右转'};
    all('[data-drive-direction]').forEach(b=>{const l=b.querySelector('.direction-name');if(l&&labels[b.dataset.driveDirection])l.textContent=labels[b.dataset.driveDirection];});
    const native=data.control_model==='driver_native_speed',targets=data.speed_targets||[],outputs=(native?data.speed_commands:data.applied_pwm)||[];
    ['driveSpeedLeft','driveSpeedRight'].forEach((id,i)=>text(id,data.connected&&targets[i*2]!=null?targets[i*2]:'—'));
    for(let i=0;i<4;i++)text('driveOutputM'+(i+1),data.connected&&outputs[i]!=null?outputs[i]+' / 目标 '+(targets[i]==null?'—':targets[i]):'—');
    text('groundDriveReason',data.capabilities&&data.capabilities.ground_reason||'当前只完成过麦轮悬空检查，落地方向和跑偏仍待验证。');
    const fault=data.controller_fault||0;text('driveControllerFault',fault?(fault<=4?`M${fault}持续无转动反馈，整组已停机`:'控制器已停机，故障码 '+fault):'无当前控制器故障');speedHint();
  }
  function localStop(message){epoch++;session=null;pendingZero=false;lastMessage=message;resetInput();text('driveFeedback',message);}
  async function stop(){localStop('已归零，正在等待主控停止回执…');try{const d=await api.post('drive/stop',{},2400);if(!d.stopped)throw Error('没有收到停止确认');lastMessage='主控已确认零输出，遥控已锁定。';text('driveFeedback',lastMessage);}catch(e){lastMessage='停止未确认，请使用实物断电：'+e.message;text('driveFeedback',lastMessage);}}
  async function start(){
    if(busy||session||!available)return;busy=true;lastMessage='';const e=++epoch;paint();
    try{const d=await api.post('drive/start',{mode:'manual'},2400);if(e!==epoch||document.hidden){api.beacon('drive/stop');return;}
      if(typeof d.session!=='string'||!d.session)throw Error('控制会话缺失');session=d.session;sequence=lastBrakeSeq=0;lastSent=performance.now();resetInput();text('driveFeedback','遥控已开启。按住才运动，松手回中归零。');
    }catch(error){if(e===epoch)localStop('未开启：'+error.message);}finally{busy=false;paint();}
  }
  async function send(zero=false){
    if(!session||document.hidden||braking)return;if(sending){if(zero)pendingZero=true;return;}
    const filtered=response.step(zero?[0,0,0]:[throttle,strafe,turn],performance.now(),soft());
    const e=epoch,sid=session,payload={session:sid,seq:++sequence,throttle:filtered[0],strafe:filtered[1],turn:filtered[2],limit:Number($('driveLimit').value)};
    if(zero)pendingZero=false;sending=true;lastSent=performance.now();
    try{await api.post('drive/set',payload,1800);}catch(error){if(e===epoch&&payload.seq>lastBrakeSeq)await stop();}
    finally{sending=false;if(e===epoch&&pendingZero){pendingZero=false;send(!holding);}}
  }
  async function brake(){
    if(!session||braking)return;response.reset(performance.now());braking=true;const e=epoch,seq=++sequence;lastBrakeSeq=seq;
    try{await api.post('drive/brake',{session,seq},1800);}catch(error){if(e===epoch)await stop();}finally{braking=false;lastSent=performance.now();}
  }
  function release(zone,id){
    if(zone==='move'){if(movePointer!==id)return;movePointer=null;moveValue=[0,0];}else{if(spinPointer!==id)return;spinPointer=null;spinValue=0;}
    input();if(holding)send();else brake();
  }
  function position(node,event){const r=node.getBoundingClientRect();return [(event.clientX-r.left-r.width/2)/(r.width*.36),(r.top+r.height/2-event.clientY)/(r.height*.36)];}
  function move(event){const p=position(pad,event),scale=Math.max(1,Math.hypot(p[0],p[1]));moveValue=[p[1]/scale*100,p[0]/scale*100];input();}
  function rotate(event){spinValue=clamp(position(spinPad,event)[0]*100,100);input();}
  function hold(zone,node,event,update){
    if(!session||event.button>0||zone==='spin'&&!mecanum||(zone==='move'?movePointer:spinPointer)!==null)return;
    event.preventDefault();if(zone==='move')movePointer=event.pointerId;else spinPointer=event.pointerId;
    node.setPointerCapture(event.pointerId);update(event);send();
  }
  [pad,spinPad].forEach(node=>protectHoldControl(node));
  pad.addEventListener('pointerdown',e=>hold('move',pad,e,move));pad.addEventListener('pointermove',e=>{if(e.pointerId===movePointer)move(e);});
  spinPad.addEventListener('pointerdown',e=>hold('spin',spinPad,e,rotate));spinPad.addEventListener('pointermove',e=>{if(e.pointerId===spinPointer)rotate(e);});
  ['pointerup','pointercancel','lostpointercapture'].forEach(name=>{pad.addEventListener(name,e=>release('move',e.pointerId));spinPad.addEventListener(name,e=>release('spin',e.pointerId));});
  all('[data-drive-direction]').forEach(button=>{
    protectHoldControl(button);const name=button.dataset.driveDirection,zone=name.startsWith('rotate')?'spin':'move';
    button.addEventListener('pointerdown',event=>hold(zone,button,event,()=>{
      if(zone==='spin')spinValue=name==='rotateRight'?100:-100;
      else{const d={forward:[100,0],back:[-100,0],left:[0,-100],right:[0,100],forwardLeft:[100,-100],forwardRight:[100,100],backLeft:[-100,-100],backRight:[-100,100]};moveValue=d[name];}input();
    }));
    ['pointerup','pointercancel','lostpointercapture'].forEach(event=>button.addEventListener(event,e=>release(zone,e.pointerId)));
  });
  const accepted=k=>['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','w','a','s','d','q','e',' '].includes(k);
  [pad,spinPad].forEach(node=>node.addEventListener('keydown',event=>{const k=event.key.length===1?event.key.toLowerCase():event.key;if(!session||!accepted(k))return;event.preventDefault();if(k===' '){stop();return;}keys.add(k);input();send();}));
  addEventListener('keyup',event=>{const k=event.key.length===1?event.key.toLowerCase():event.key;if(!keys.has(k))return;event.preventDefault();keys.delete(k);input();if(holding)send();else brake();});
  [pad,spinPad].forEach(node=>node.addEventListener('blur',()=>{if(!keys.size)return;keys.clear();input();if(holding)send();else brake();}));
  $('driveBrake').addEventListener('click',()=>{resetInput();brake();});$('startDrive').addEventListener('click',start);$('stopDrive').addEventListener('click',stop);
  all('[data-stop]').forEach(button=>button.addEventListener('click',stop));$('driveLimit').addEventListener('input',()=>{speedHint();if(session)send(!holding);});
  function responseMode(){const limit=$('driveLimit');limit.max=soft()?'30':'100';if(soft()&&Number(limit.value)>30)limit.value='30';resetInput();speedHint();if(session)brake();}
  if(softControl){softControl.addEventListener('change',responseMode);responseMode();}
  function render(data,version=epoch){
    if(version!==epoch)return; // Ignore status requests made before the current control owner.
    feedback(data);const fresh=Boolean(data.connected)&&Number.isFinite(data.age_ms)&&data.age_ms>=0&&data.age_ms<2500;
    available=fresh&&Boolean(data.capabilities&&data.capabilities.drive_control===true);lastStatus=fresh?performance.now():0;
    const d=data.drive||{};badge('driveState',session?'遥控已开启':available?'可以开启':fresh?'等待驱动就绪':'主控未连接',session?'online':'');
    if(session&&(!fresh||!available||!d.active)){const message=!fresh?'主控数据已过期，已请求停止。':d.stop_message||(!available?'驱动许可失效，已请求停止。':'遥控会话已停止，请重新开启。');leave(message);}
    else if(!session&&!available)text('driveFeedback',data.capabilities&&data.capabilities.drive_reason||'连接主控并开始记录后，才可开启遥控。');
    else if(!session&&!busy)text('driveFeedback',lastMessage||d.stop_message||'已就绪。先开启遥控，再按住摇杆。');paint();
  }
  function leave(message='页面离开，已请求停止。'){const had=Boolean(session)||busy;localStop(message);if(had)api.beacon('drive/stop');}
  const timer=setInterval(()=>{if(!session||document.hidden||braking)return;if(!lastStatus||performance.now()-lastStatus>2500){leave();return;}if(performance.now()-lastSent>=120)send(!holding);},40);
  // Native focus changes should zero held input, not force another ARM. Hidden
  // pages still take app.js's full STOP path; a new touch is required to move.
  addEventListener('blur',()=>{if(session){resetInput();brake();text('driveFeedback','已暂停输入并归零；回到页面后可重新按住摇杆。');}});paint();feedback();
  return {render,stop,leave,version:()=>epoch,destroy(){leave();clearInterval(timer);}};
}
