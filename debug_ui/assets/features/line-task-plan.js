import {lineView} from './line.js';
/* Explicit task owner. The second mode is an honest preparation view: no motion API. */
export function createLineTaskPlan(api){
  const root=document.getElementById('lineTaskPlan');if(!root)return {render(){},leave(){},stop(){},version(){return 0;}};
  const branch=document.getElementById('lineTaskBranch'),pace=document.getElementById('lineTaskPace'),duration=document.getElementById('lineTaskDuration'),side=document.getElementById('lineTaskSide');
  const startButton=document.getElementById('startLineTask'),stopButton=document.getElementById('stopLineTask'),feedback=document.getElementById('lineTaskFeedback');
  let session=null,epoch=0,busy=false,sending=false,available=false,supported=false,mcuActive=false,lastState=0,loopDefaults=false,mode='follow',latest={},pcOnly=false;
  const modes=Array.from(document.querySelectorAll('[data-follow-mode]'));
  function write(id,text){const node=document.getElementById(id);if(node)node.textContent=text;}
  function ready(id,value){const node=document.getElementById(id);if(node)node.setAttribute('data-ready',String(value));}
  const key='zhixing-line-task-plan-v1';
  try{const p=JSON.parse(localStorage.getItem(key)||'{}');if(['stop','left','straight','right','loop'].includes(p.branch))branch.value=p.branch;if(['40','60'].includes(String(p.pace)))pace.value=String(p.pace);if(['0','5','10'].includes(String(p.duration)))duration.value=String(p.duration);}catch(ignored){}
  // Installation side deliberately starts unconfirmed after each page load.
  side.value='0';
  function paint(){
    const locked=busy||Boolean(session)||mcuActive;
    startButton.disabled=locked||mode==='fixed'||!available||side.value==='0';
    stopButton.disabled=!supported&&!session;
    for(const field of [branch,pace,duration,side])field.disabled=locked||mode==='fixed';
    for(const button of modes){button.disabled=locked;button.setAttribute('aria-pressed',String(button.getAttribute('data-follow-mode')===mode));}
    const option=pace.querySelector&&pace.querySelector('option[value="60"]');if(option)option.disabled=branch.value==='loop';
    write('routeModeDescription',mode==='fixed'?'车头保持启动时的方向，前后与横移共同沿线移动。此模式还没有接入自动执行。':'八路探头判断线的位置，主控持续调整方向。偏线自动纠正，丢线低速找回。');
    const requirements=document.getElementById('routeFixedRequirements');if(requirements)requirements.hidden=mode!=='fixed';
    startButton.textContent=mode==='fixed'?'固定朝向尚未就绪':branch.value==='loop'?'开始随线转向':'开始路口循线';
    ready('routeReadySide',side.value!=='0');
  }
  function save(){
    if(branch.value!=='loop'&&duration.value==='0')duration.value='5';
    if(branch.value==='loop')pace.value='40';
    try{localStorage.setItem(key,JSON.stringify({branch:branch.value,pace:Number(pace.value),duration:Number(duration.value)}));document.getElementById('lineTaskPlanSaved').textContent='路线预设已保存在本机。';}
    catch(ignored){document.getElementById('lineTaskPlanSaved').textContent='本次路线预设未能持久保存。';}render(latest);
  }
  for(const button of modes)button.addEventListener('click',()=>{if(busy||session||mcuActive)return;mode=button.getAttribute('data-follow-mode');render(latest);});
  function jump(buttonId,targetId,expand){const button=document.getElementById(buttonId);if(button)button.addEventListener('click',()=>{if(targetId==='driveCard'){const tab=document.querySelector('[data-control-mode="drive"]');if(tab)tab.click();}const target=document.getElementById(targetId);if(!target)return;if(expand)target.open=true;target.scrollIntoView({behavior:'smooth',block:'start'});});}
  jump('routeShowSensors','lineCard',false);jump('routeShowManual','driveCard',true);
  for(const field of [branch,pace,duration,side])field.addEventListener('change',save);
  async function stop(){const had=Boolean(session)||supported;epoch++;session=null;paint();if(!had)return;
    feedback.textContent='正在等待主控停止回执…';
    try{const r=await api.post('line-task/stop',{},2400);if(!r.stopped)throw Error('没有收到巡线停止确认');mcuActive=false;feedback.textContent='主控已确认巡线停止。';}
    catch(error){feedback.textContent='停止未确认：'+error.message;}paint();
  }
  async function start(){if(startButton.disabled)return;const e=++epoch;busy=true;paint();feedback.textContent='正在核对主控并启动巡线…';
    try{const r=await api.post('line-task/start',{branch:['stop','left','straight','right','loop'].indexOf(branch.value),speed:Number(pace.value),duration_ms:Number(duration.value)*1000,x1_left:Number(side.value)},2400);
      if(e!==epoch||document.hidden){await api.post('line-task/stop');return;}if(!r.session)throw Error('缺少巡线会话回执');session=r.session;feedback.textContent=branch.value==='loop'?'正在按黑线自动巡航；点击停止结束。':'巡线任务已由主控接受。';}
    catch(error){if(e===epoch){feedback.textContent='未启动：'+error.message;session=null;}}
    finally{busy=false;paint();}
  }
  function leave(){const had=Boolean(session)||busy;epoch++;session=null;paint();if(had){api.beacon('line-task/stop');feedback.textContent='页面离开，已请求撤销巡线任务。';}}
  const reasons={2:'循迹数据超时',3:'丢线后未能在限定时间内找回',4:'前方距离或保护条件不满足',5:'到达所选时限',6:'黑色区域过宽或存在分叉',7:'路口转向超时',9:'电机反馈、电压或执行器故障，请查看电机状态',10:'控制连接中断，未收到续租'};
  function render(data,requestEpoch=epoch){if(requestEpoch!==epoch)return;latest=data;const t=data.line_task||{},fresh=Boolean(data.connected)&&Number.isFinite(data.age_ms)&&data.age_ms>=0&&data.age_ms<1500;
    if(t.loop_supported&&!loopDefaults&&!session&&!busy){branch.value='loop';pace.value='40';duration.value='0';loopDefaults=true;}
    if(t.trial&&!session&&!busy){branch.value='stop';pace.value='40';duration.value='5';}
    supported=fresh&&t.supported===true;available=fresh&&t.available===true&&(!data.line_calibration||(data.line_calibration.ready&&!data.line_calibration.busy));mcuActive=fresh&&t.mcu_active===true;if(fresh)lastState=performance.now();
    pcOnly=Boolean(data.connected)&&t.supported===false&&(!data.line_calibration)&&Boolean(data.firmware||data.mode==='PC_COMPREHENSIVE');
    const view=fresh?lineView(data):{valid:false,position:null};
    write('routeLineOffset',view.position===null?'—':Math.abs(view.position)<.12?'接近中央':(view.position<0?'X1端 ':'X8端 ')+Math.round(Math.abs(view.position)*100)+'%');
    write('routeLineCount',view.valid?view.count+' / 8 路':'— / 8 路');
    write('routeExecution',!fresh?'未连接':pcOnly?'需手机 P7':supported?'手机 → 主控':'暂不可执行');
    ready('routeReadyLink',fresh&&view.valid);ready('routeReadyCalibration',fresh&&Boolean(data.line_calibration&&data.line_calibration.ready&&!data.line_calibration.busy));
    const state=document.getElementById('routeTaskState');if(state){state.textContent=mode==='fixed'?'待接入':!fresh?'未连接':t.state===5?'故障已停':mcuActive?(t.state===3?'找线中':'跟随中'):available?'等待开始':pcOnly?'P9 监测':'等待就绪';state.setAttribute('data-state',t.state===5&&fresh?'fault':mcuActive?(t.state===3?'search':'running'):'idle');}
    if(session&&(!fresh||!t.active)){leave();feedback.textContent=t.state===4?'本轮巡线已结束。':t.state===5?'已停车：'+(reasons[t.reason]||'保护条件触发'):'巡线会话已撤销，需重新开启。';}
    else if(session&&branch.value==='loop')feedback.textContent=t.state===3?'正在低速转向找线；找回后自动继续，可手动停止。':'环线巡航中；根据八路位置自动过弯。';
    else if(!session&&!busy&&fresh&&t.state===5)feedback.textContent='已停车：'+(reasons[t.reason]||'保护条件触发')+'；处理后可重新开始。';
    else if(!session&&!busy)feedback.textContent=mode==='fixed'?'尚不能启动：需要持续航向保持和二维路线反馈。可先用上方手动控制验证平移。':mcuActive?'主控正在执行循线；需要结束时点击停止。':!fresh?'请先连接主控并开始记录。':pcOnly?'电脑 P9 当前用于监测和手动控制。自动循线请把小手机接回 P7，在手机或平板页面开始。':!available?(t.message||'当前服务未提供自动循迹执行。'):side.value==='0'?'先确认下方“X1所在车侧”，再开始随线转向。':t.trial?'首轮低速5秒试跑；遇路口停车。':branch.value==='loop'&&duration.value==='0'?'持续跟随就绪；偏线纠正、丢线转向找回，前方测距仅提示。点击停止结束。':'巡线就绪；本次限时 '+duration.value+' 秒。';
    if(supported)for(const b of document.querySelectorAll('[data-stop]'))b.disabled=false;paint();
  }
  startButton.addEventListener('click',start);stopButton.addEventListener('click',stop);
  for(const b of document.querySelectorAll('[data-stop]'))b.addEventListener('click',stop);
  setInterval(async()=>{if(!session||sending||document.hidden)return;if(!lastState||performance.now()-lastState>2000){leave();return;}
    const e=epoch;const current=session;sending=true;try{await api.post('line-task/heartbeat',{session:current},1200);}catch(error){if(e===epoch)await stop();}finally{sending=false;}
  },150);
  addEventListener('blur',()=>{if(session)leave();});paint();return {render,leave,stop,version:()=>epoch};
}
