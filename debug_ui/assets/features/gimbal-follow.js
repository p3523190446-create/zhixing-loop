import {$,all} from '../core/dom.js';

/** Browser owns the enable lease; fresh-frame control runs on the phone. */
export function createGimbalFollow(api,gimbal){
  const root=document.createElement('section');root.id='gimbalFollowPanel';root.className='gimbal-follow-panel';root.hidden=true;
  root.innerHTML=`<div class="card-heading"><h2>云台色块跟随</h2><span id="followState" class="badge">尚未开启</span></div>
    <p class="hint">选择红、绿或蓝色目标，等待连续锁定，再点击开始。看丢时保持位置，所选颜色稳定重锁后继续。多个同色物体可能切换，展示时使用单个明显色块。</p>
    <ol class="hint" aria-label="跟随准备进度"><li id="followReadyBoard">等待主控状态</li><li id="followReadyTarget">等待色块锁定</li><li id="followReadyGimbal">等待云台准备</li><li id="followReadyConfirm">等待方向与范围确认</li></ol>
    <label class="follow-confirm"><input id="followConfirmed" type="checkbox">车已停稳，我已核对云台方向和活动范围</label>
    <div class="button-row"><button id="followStart" class="button" disabled>开始双轴跟随</button><button id="followStop" class="button secondary" disabled>停止跟随</button></div>
    <p id="followMessage" class="hint" role="status" aria-live="polite">等待本页手动控制和真实色块锁定。</p>
    <details class="fold-tools"><summary>跟随方向与范围<span class="fold-hint">展开</span></summary><div class="fold-content">
      <label>跟随方式<select id="followAxes"><option value="yaw">仅水平</option><option value="both" selected>水平＋俯仰</option></select></label>
      <label>水平方向<select id="followYaw"><option value="-1">本车实测方向</option><option value="1">相反方向</option></select></label>
      <label>俯仰方向<select id="followPitch"><option value="1">正常</option><option value="-1">反向</option></select></label>
      <p class="hint">若越追越偏，先停止，再切换对应方向。跟随使用已保存的云台范围；向下偏移对应低头，向上偏移对应抬头。</p>
      <p id="followBounds" class="hint"></p>
    </div></details>`;
  $('phoneVisionPanel').appendChild(root);
  let supported=false,session=null,pending=false,polling=false,beating=false,epoch=0,last=null;
  function controls(){
    const ready=gimbal.followReadiness();
    $('followReadyBoard').textContent=last&&last.available?'✓ 主控已连接，车轮停止会话已释放':'① '+(last&&last.block_reason||'连接主控并开始记录，再点四驱停止');
    $('followReadyTarget').textContent=last&&last.target_locked?'✓ 所选色块已连续锁定':'② 开启相机，选择红、绿或蓝色，把对应色块放进画面';
    $('followReadyGimbal').textContent=ready.ready?'✓ 云台已准备，可使用保存的中位或本页当前位置':'③ '+ready.message;
    $('followReadyConfirm').textContent=$('followConfirmed').checked?'✓ 方向和活动范围已确认':'④ 勾选下方的方向与活动范围确认';
    $('followStart').disabled=Boolean(!supported||pending||session||!last||last.active||!last.available||!last.target_locked||!ready.ready||!$('followConfirmed').checked);
    $('followStart').textContent=pending?'正在准备…':ready.fromCenter?'从中位跟随':'交接并跟随';
    $('followStop').disabled=Boolean(!session||pending);
    ['followAxes','followYaw','followPitch','followConfirmed'].forEach(id=>{$(id).disabled=Boolean(session||pending);});
  }
  function render(data){
    last=data;if(session&&!data.active)session=null;
    const ready=gimbal.followReadiness(),reason=data.message&&data.message!=='尚未启动'?data.message+'。 ':'';
    $('followState').textContent=data.active?(data.state==='HOLDING'?'暂时保持':data.state==='CENTERED'?'目标已居中':'正在对准中心'):data.target_locked?'已锁定，等待启动':'未在跟随';
    $('followMessage').textContent=data.active?(session?(data.state==='HOLDING'?'等待所选颜色重新锁定；云台保持当前位置，重新锁定后继续。':data.message+'。相机过期、页面离开或手动停止会撤销。'):'其他页面正在跟随；可在云台控制区切回手动。'):
      !data.available?(data.block_reason||'请保持车轮停止，并连接主控开始记录。'):!data.target_locked?reason+'所选色块还没有连续锁定；识别到目标后仍需点击开始。':reason+ready.message;
    $('followBounds').textContent=data.yaw_min?'当前水平范围 '+data.yaw_min+'～'+data.yaw_max+'，俯仰 '+data.pitch_min+'～'+data.pitch_max+'（控制值）；自动限速 ' + data.max_tracking_rate_us_s + '微秒/秒。':'';
    controls();
  }
  async function poll(){if(!supported||pending||polling||document.hidden)return;polling=true;const e=epoch;try{const d=await api.get('gimbal-follow/status',1800);if(e===epoch&&!pending)render(d);}catch(error){if(e===epoch&&!pending){$('followState').textContent='状态未确认';$('followMessage').textContent=error.message;}}finally{polling=false;controls();}}
  $('followStart').addEventListener('click',async()=>{
    if(pending||!$('followConfirmed').checked)return;let offered=null;pending=true;const e=++epoch;controls();
    try{
      offered=await gimbal.prepareForFollow();if(e!==epoch||document.hidden){api.post('gimbal/stop',{session:offered.session}).catch(()=>{});return;}
      const data=await api.post('gimbal-follow/start',{manual_session:offered.session,confirmed:true,yaw_sign:Number($('followYaw').value),pitch_sign:Number($('followPitch').value),both_axes:$('followAxes').value==='both'},2800);
      if(e!==epoch||document.hidden){if(data.session)api.post('gimbal-follow/stop',{session:data.session}).catch(()=>{});return;}
      if(!data.session)throw Error('跟随开启回执缺少会话');epoch++;session=data.session;render(data);
    }catch(error){if(e===epoch){if(offered)await gimbal.recoverFromFollow(offered);$('followMessage').textContent='跟随未开启：'+error.message;}}
    finally{pending=false;controls();poll();}
  });
  async function stop(){if(!session)return;const token=session;session=null;epoch++;pending=true;controls();try{const d=await api.post('gimbal-follow/stop',{session:token},2800);render(d);}catch(error){$('followMessage').textContent='停止回执未确认：'+error.message;}finally{pending=false;controls();poll();}}
  $('followStop').addEventListener('click',stop);$('followConfirmed').addEventListener('change',controls);
  function leave(){const token=session;session=null;epoch++;pending=false;if(token)api.beacon('gimbal-follow/stop',{session:token});controls();}
  all('[data-stop]').forEach(button=>button.addEventListener('click',()=>{session=null;epoch++;controls();}));
  const timer=setInterval(poll,300),heartbeat=setInterval(async()=>{if(!session||beating||document.hidden)return;beating=true;const token=session,e=epoch;try{await api.post('gimbal-follow/heartbeat',{session:token},1800);}catch(error){if(e===epoch){session=null;$('followMessage').textContent='跟随会话已撤销：'+error.message;controls();}}finally{beating=false;}},400);
  return {start(info){supported=Boolean(info.gimbal_follow);root.hidden=!supported;if(supported)poll();},leave,destroy(){leave();clearInterval(timer);clearInterval(heartbeat);}};
}
