/** Capture and quality checks live in the phone service, across page reloads. */
export function createLineCalibration(api){
  const root=document.getElementById('lineCalibration');if(!root)return {start(){},render(){}};
  const ids=['Floor','Black','Save'],buttons=ids.map(id=>document.getElementById('lineCal'+id));
  const message=document.getElementById('lineCalMessage'),badge=document.getElementById('lineCalBadge'),progress=document.getElementById('lineCalProgress'),cancel=document.getElementById('lineCalCancel');
  let enabled=false,sending=false,fresh=false,state={},failure='';
  function paint(){
    root.hidden=!enabled;if(!enabled)return;
    const busy=state.busy===true,available=fresh&&state.supported===true&&!busy&&!sending;
    buttons[0].disabled=!available;buttons[1].disabled=!available||!state.floor_done;buttons[2].disabled=!available||!state.floor_done||!state.black_done;
    cancel.hidden=!busy;cancel.disabled=sending;
    badge.textContent=busy?'处理中':state.ready?'已应用':state.saved?'已存手机':'待标定';badge.dataset.ready=String(state.ready===true);
    message.textContent=failure||(!fresh?'请先连接主控并开始记录；上电后约等20秒。':state.message||'等待标定服务');
    progress.hidden=!state.surface;progress.value=Math.max(0,6000-(state.remaining_ms||0));
    for(let i=0;i<3;i++)document.getElementById('lineCal'+ids[i]+'Step').classList.toggle('is-done',i===0?state.floor_done===true:i===1?state.black_done===true:state.ready===true);
    if(state.surface)message.textContent+=' · '+Math.ceil((state.remaining_ms||0)/1000)+'秒 · '+(state.samples||0)+'组';
  }
  async function act(action){if(sending)return;sending=true;failure='';paint();try{state=await api.post('line-calibration/'+action,{},5000);}catch(error){failure=error.message;}finally{sending=false;paint();}}
  buttons.forEach((b,i)=>b.addEventListener('click',()=>{if(!b.disabled)act(['floor','black','save'][i]);}));cancel.addEventListener('click',()=>act('cancel'));
  return {start(info){enabled=info.line_calibration===true;paint();},render(data){fresh=data.connected===true&&Number.isFinite(data.age_ms)&&data.age_ms>=0&&data.age_ms<1500;if(data.line_calibration){state=data.line_calibration;if(!sending)failure='';}paint();}};
}
