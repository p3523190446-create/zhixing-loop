import {$,all,text,badge,number} from '../core/dom.js';
/** Recording operations and list refresh; playback has a separate module. */
export function createRecording(api) {
  let state={active:false,finishing:false},busy=false,polling=false,lastSaved=null,ready=false,owned=false,intent=0;
  function buttons(){all('[data-record-start]').forEach(b=>b.disabled=!ready||busy||state.active||state.finishing);all('[data-record-stop]').forEach(b=>b.disabled=!state.active||busy);}
  function render(d){state=d;badge('recordBadge',d.active?'记录中':d.finishing?'正在保存':d.id?'已保存':'未记录',d.active?'online':d.error?'bad':'');text('liveRecordBadge',d.active?'● 原始通信记录中':d.finishing?'正在保存…':'未记录');text('recordInfo',number(d.duration_s||0)+' 秒 · '+(d.frames||0)+' 帧 · '+(d.samples||0)+' 条状态 · '+number((d.bytes||0)/1048576)+' MB'+(d.dropped_frames?' · 丢帧 '+d.dropped_frames:''));buttons();}
  async function refresh(){try{const list=await api.get('record/list');if(!Array.isArray(list))throw Error('记录列表格式错误');const old=$('recordList').value;while($('recordList').firstChild)$('recordList').removeChild($('recordList').firstChild);list.filter(s=>s.state!=='RECORDING').forEach(s=>{const option=document.createElement('option');option.value=s.id;option.textContent=String(s.started_at||s.id).slice(0,19).replace('T',' ')+' · '+number(s.duration_s||0)+' 秒'+(['ERROR','INTERRUPTED'].includes(s.state)?' · 不完整':'')+(s.dropped_frames?' · 有丢帧':'');$('recordList').append(option);});if(!$('recordList').options.length){const option=document.createElement('option');option.value='';option.textContent='暂无已保存记录';$('recordList').append(option);}if(Array.from($('recordList').options).some(o=>o.value===old))$('recordList').value=old;}catch(e){text('recordMessage','记录列表暂不可用：'+e.message);}}
  async function poll(){if(polling)return;polling=true;try{const d=await api.get('record/status');render(d);if(!d.active&&!d.finishing&&d.id!==lastSaved){lastSaved=d.id;owned=false;if(d.id){text('recordMessage',d.error?'保存异常：'+d.error:'已保存：'+(d.reason||'正常结束'));refresh();}}}catch(e){ready=false;buttons();text('recordMessage','记录状态暂不可用：'+e.message);}finally{polling=false;}}
  async function start(automatic=false){
    if(busy)return;const e=intent;busy=true;buttons();
    try{const d=await api.post('record/start',{},7000);if(e!==intent||document.hidden){await api.post('record/stop',{},7000);return;}owned=true;render(d);text('recordMessage',automatic?'画质切换完成，已续录新段。':'正在记录主控原始通信与状态。');}
    catch(error){api.beacon('record/stop');text('recordMessage','开始记录未确认：'+error.message);throw error;}finally{busy=false;buttons();}
  }
  async function stop(explicit=true){if(explicit)intent++;if(busy&&explicit){api.beacon('record/stop');return;}busy=true;buttons();try{render(await api.post('record/stop',{},7000));const until=performance.now()+7000;while(state.finishing&&performance.now()<until){await new Promise(r=>setTimeout(r,150));render(await api.get('record/status'));}if(state.finishing)throw Error('记录仍在保存，请稍后再操作');owned=false;await refresh();}finally{busy=false;buttons();}}
  all('[data-record-start]').forEach(b=>b.addEventListener('click',()=>start().catch(()=>{})));
  all('[data-record-stop]').forEach(b=>b.addEventListener('click',()=>stop().catch(e=>text('recordMessage',e.message))));
  $('refreshRecords').addEventListener('click',refresh);
  const timer=setInterval(poll,1000);poll();refresh();
  function leave(){/* Background recording belongs to the phone service; keep running. */}
  return {start,stop,refresh,poll,leave,isActive:()=>state.active,getIntent:()=>intent,
    setReady(value){ready=Boolean(value);buttons();},destroy(){leave();clearInterval(timer);}};
}
