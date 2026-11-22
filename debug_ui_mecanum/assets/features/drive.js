import {$,all,text,badge,clamp} from '../core/dom.js';
import {protectHoldControl} from '../core/control-touch.js';

/** A dead-man drive stick. Fresh set commands, never a heartbeat, sustain motion. */
export function createDrive(api) {
  let session=null,epoch=0,busy=false,sending=false,pointer=null,keys=new Set();
  let mecanum=false,strafe=0;
  let throttle=0,turn=0,sequence=0,lastStatus=0,lastSent=0,pendingRelease=false;
  let available=false,holding=false,nativeModel=false,nativeSpeedMax=120;
  let braking=false,lastBrakeSeq=0;
  function paint(){
    $('driveThumb').style.left=(50+(mecanum?strafe:turn)*.36)+'%';
    $('driveThumb').style.top=(50-throttle*.36)+'%';
    text('driveTarget',mecanum?`前后 ${throttle} / 横移 ${strafe} / 旋转 ${turn}`:`前后 ${throttle} / 转向 ${turn}`);
    $('driveJoystick').setAttribute('aria-disabled',String(!session));
    $('startDrive').disabled=busy||Boolean(session)||!available;
    all('[data-drive-direction]').forEach(b=>b.disabled=!session);
    text('drivePermission',session?'手动拍摄':'未开启');
  }
  function resetInput(){pointer=null;keys.clear();holding=false;throttle=turn=strafe=0;paint();}
  function feedback(data={}){
    const nextMecanum=Boolean(data.capabilities&&data.capabilities.mecanum_control);
    if(nextMecanum!==mecanum&&session)leave();
    mecanum=nextMecanum;
    text('driveWestLabel',mecanum?'左移':'左转');text('driveEastLabel',mecanum?'右移':'右转');
    text('driveInputHint',mecanum?'摇杆控制平移，按钮控制旋转；方向键平移，Q / E旋转，松手归零':'按住行驶，松手归零');
    all('[data-mecanum-only]').forEach(el=>el.hidden=!mecanum);
    const labels=mecanum?{left:'左移',right:'右移',forwardLeft:'左前斜移',forwardRight:'右前斜移',backLeft:'左后斜移',backRight:'右后斜移'}:{left:'原地左转',right:'原地右转',forwardLeft:'前进左拐',forwardRight:'前进右拐',backLeft:'倒车左转',backRight:'倒车右转'};
    all('[data-drive-direction]').forEach(b=>{if(labels[b.dataset.driveDirection])b.textContent=labels[b.dataset.driveDirection];});
    nativeModel=data.control_model==='driver_native_speed';
    nativeSpeedMax=data.capabilities&&data.capabilities.driver_speed_limit||120;
    const hint=$('driveSpeedHint');if(hint)hint.textContent=`满杆目标 ${80+Math.floor(Number($('driveLimit').value)*.4)}（驱动回报单位）；直行外侧目标80–120；内侧按转向比例减速，起转后按各轮反馈调节。`;
    const cap=data.capabilities&&data.capabilities.motor_pwm_limit;if(cap&&hint)hint.textContent+=' 当前PWM命令上限 '+cap+'；驱动板含死区补偿，此数字不代表实际占空比。';
    if(nativeModel&&hint)hint.textContent='官方编码器速度闭环：当前满杆目标 '+(nativeSpeedMax>120?Math.max(60,Math.round(nativeSpeedMax*Number($('driveLimit').value)/100)):20+Number($('driveLimit').value))+'，当前速度上限 '+nativeSpeedMax+'；100%使用当前主控全部速度范围。驱动板含死区补偿，实际PWM未回报。';
    const targets=data.speed_targets||[],outputs=(nativeModel?data.speed_commands:data.applied_pwm)||[];
    ['driveSpeedLeft','driveSpeedRight'].forEach((id,i)=>{if($(id))text(id,data.connected&&targets[i*2]!=null?targets[i*2]:'—');});
    for(let i=0;i<4;i++)if($('driveOutputM'+(i+1)))text('driveOutputM'+(i+1),data.connected&&outputs[i]!=null?outputs[i]+(nativeModel?' 速度命令':' PWM')+(mecanum&&targets[i]!=null?' / 目标 '+targets[i]:''):'—');
    if($('groundDriveReason'))text('groundDriveReason',data.capabilities&&data.capabilities.ground_reason||'手动拍摄模式；地面转向待实体验证。');
    if($('driveControllerFault')){const f=data.controller_fault||0;text('driveControllerFault',f?(f<=4?`M${f}持续无转动反馈，整组已停机`:'控制器已停机，故障码 '+f):'无当前控制器故障');}
  }
  function localStop(message){epoch++;session=null;pendingRelease=false;resetInput();text('driveFeedback',message);}
  async function stop(){
    localStop('已归零，正在等待主控停止回执…');
    try{const d=await api.post('drive/stop',{},2400);if(!d.stopped)throw Error('没有收到停止确认');text('driveFeedback','主控已确认零输出；请查看车轮是否停稳。');}
    catch(error){text('driveFeedback','停止未确认，请使用实物断电：'+error.message);}
  }
  async function start(){
    if(busy||session||!available)return;
    busy=true;const e=++epoch;paint();
    try{
      const d=await api.post('drive/start',{mode:'manual'},2400);
      if(e!==epoch||document.hidden){api.beacon('drive/stop');return;}
      if(typeof d.session!=='string'||!d.session)throw Error('控制会话缺失');
      session=d.session;sequence=lastBrakeSeq=0;lastSent=performance.now();resetInput();
      text('driveFeedback','手动拍摄控制已开启。按住摇杆才持续发送；松手归零。');
    }catch(error){if(e===epoch)localStop('未开启：'+error.message);}
    finally{busy=false;paint();}
  }
  function target(forward,steer,rotation=0){
    if(!session)return;
    const dead=value=>Math.abs(value)<8?0:clamp(Math.round(value),100);
    throttle=dead(forward);strafe=mecanum?dead(steer):0;turn=mecanum?dead(rotation):dead(steer);paint();
  }
  async function send(forceZero=false){
    if(!session||document.hidden||braking)return;
    if(sending){if(forceZero)pendingRelease=true;return;}
    const e=epoch,sid=session;
    // Sample current input immediately before dispatch; stale queued vectors are never replayed.
    const payload={session:sid,seq:++sequence,throttle:forceZero?0:throttle,
      turn:forceZero?0:turn,strafe:forceZero?0:strafe,limit:Number($('driveLimit').value)};
    if(forceZero)pendingRelease=false;
    sending=true;lastSent=performance.now();
    try{await api.post('drive/set',payload,1800);}
    catch(error){if(e===epoch&&payload.seq>lastBrakeSeq)await stop();}
    finally{sending=false;if(e===epoch&&pendingRelease){pendingRelease=false;send(true);}}
  }
  async function release(){
    if(!session||braking)return;resetInput();braking=true;const e=epoch,seq=++sequence;lastBrakeSeq=seq;
    try{await api.post('drive/brake',{session,seq},1800);}
    catch(error){if(e===epoch)await stop();}
    finally{braking=false;lastSent=performance.now();}
  }
  function move(event){const rect=$('driveJoystick').getBoundingClientRect();
    const x=(event.clientX-rect.left-rect.width/2)/(rect.width*.4),y=(rect.top+rect.height/2-event.clientY)/(rect.height*.4);
    const scale=Math.max(1,Math.hypot(x,y));target(y/scale*100,x/scale*100);
  }
  const pad=$('driveJoystick');
  protectHoldControl(pad);
  pad.addEventListener('pointerdown',event=>{
    if(!session||pointer!==null||event.button>0)return;event.preventDefault();
    pointer=event.pointerId;holding=true;pad.setPointerCapture(pointer);move(event);send();
  });
  pad.addEventListener('pointermove',event=>{if(event.pointerId===pointer)move(event);});
  ['pointerup','pointercancel','lostpointercapture'].forEach(name=>pad.addEventListener(name,event=>{if(event.pointerId===pointer)release();}));
  function keyTarget(){holding=keys.size>0;target((keys.has('ArrowUp')?100:0)-(keys.has('ArrowDown')?100:0),(keys.has('ArrowRight')?100:0)-(keys.has('ArrowLeft')?100:0),mecanum?((keys.has('e')?100:0)-(keys.has('q')?100:0)):0);}
  pad.addEventListener('keydown',event=>{
    if(!session||!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','q','e',' '].includes(event.key))return;
    event.preventDefault();if(event.key===' '){stop();return;}keys.add(event.key);keyTarget();send();
  });
  pad.addEventListener('keyup',event=>{if(!keys.has(event.key))return;event.preventDefault();keys.delete(event.key);keyTarget();if(!holding)release();});
  pad.addEventListener('blur',()=>{if(holding)release();});
  all('[data-drive-direction]').forEach(button=>{
    protectHoldControl(button);
    button.addEventListener('pointerdown',event=>{
      if(!session||pointer!==null||event.button>0||event.isPrimary===false)return;
      event.preventDefault();pointer=event.pointerId;holding=true;button.setPointerCapture(event.pointerId);
      const directions={forward:[100,0],back:[-100,0],left:[0,-100],right:[0,100],forwardLeft:[100,-65],forwardRight:[100,65],backLeft:[-100,-65],backRight:[-100,65]};
      if(mecanum){
        Object.assign(directions,{forwardLeft:[100,-100],forwardRight:[100,100],backLeft:[-100,-100],backRight:[-100,100],rotateLeft:[0,0,-100],rotateRight:[0,0,100]});
      }
      const v=directions[button.dataset.driveDirection];if(v){target(...v);send();}
    });
    ['pointerup','pointercancel','lostpointercapture'].forEach(name=>button.addEventListener(name,event=>{if(holding&&event.pointerId===pointer)release();}));
  });
  $('startDrive').addEventListener('click',start);$('stopDrive').addEventListener('click',stop);
  all('[data-stop]').forEach(button=>button.addEventListener('click',stop));
  $('driveLimit').addEventListener('input',()=>{text('driveLimitValue',$('driveLimit').value+'%');const hint=$('driveSpeedHint');if(hint)hint.textContent=nativeModel?'官方编码器速度闭环：当前满杆目标 '+(nativeSpeedMax>120?Math.max(60,Math.round(nativeSpeedMax*Number($('driveLimit').value)/100)):20+Number($('driveLimit').value))+'，当前速度上限 '+nativeSpeedMax+'；实际PWM未回报。':`满杆目标 ${80+Math.floor(Number($('driveLimit').value)*.4)}（驱动回报单位）；转弯内侧按比例减速。`;if(session)send(!holding);});
  function render(data,version=epoch){
    feedback(data);
    const fresh=Boolean(data.connected)&&Number.isFinite(data.age_ms)&&data.age_ms>=0&&data.age_ms<2500;
    available=fresh&&Boolean(data.capabilities&&data.capabilities.drive_control===true);lastStatus=fresh?performance.now():0;
    const d=data.drive||{};
    badge('driveState',session?'手动拍摄':available?'可开启遥控':fresh?'固件未开放':'主控未连接',session?'online':'');
    if(session&&(!fresh||!available||version===epoch&&!d.active)){leave();text('driveFeedback','主控断连、已停止或许可失效，请重新核对后开启。');}
    else if(!session&&!available)text('driveFeedback',data.capabilities&&data.capabilities.drive_reason||'需要手动拍摄固件及新鲜主控状态。');
    else if(!session&&!busy)text('driveFeedback','手动拍摄模式就绪；按住行驶，松手归零。测距只提示。');
    if(mecanum){text('driveSpeedHint','麦轮：平移和旋转合成四轮独立目标；当前档位 '+$('driveLimit').value+'%，单位沿用驱动回报，尚未实车验收。');}
    paint();
  }
  function leave(){const had=Boolean(session)||busy;localStop('页面离开或失去焦点，已请求停止。');if(had)api.beacon('drive/stop');}
  // The steady stream of vectors is the dead-man signal. Stationary sessions renew only a zero vector.
  const timer=setInterval(()=>{
    if(!session||document.hidden||braking)return;
    if(!lastStatus||performance.now()-lastStatus>2500){leave();return;}
    if(performance.now()-lastSent>=120)send(!holding);
  },40);
  addEventListener('blur',()=>{if(session)leave();});
  paint();feedback();
  return {render,stop,leave,version:()=>epoch,destroy(){leave();clearInterval(timer);}};
}
