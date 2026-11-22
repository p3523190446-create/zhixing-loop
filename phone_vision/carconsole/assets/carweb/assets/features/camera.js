import {$,text,badge} from '../core/dom.js';
/** Owns preview frames, automatic settings switching and recording continuation. */
export function createCamera(api, recording, availability) {
  let supported=false,wanted=false,pending=false,epoch=0,framePending=false,pollPending=false;
  let url=null,seq=null,period=1000/15,lastFetch=0,previewTimes=[],choiceTimer=null;
  function clear(message){$('cameraImage').hidden=true;$('cameraImage').removeAttribute('src');$('cameraPlaceholder').hidden=false;$('cameraPlaceholder').textContent=message;if(url)URL.revokeObjectURL(url);url=null;}
  function buttons(){$('startCamera').disabled=!supported||wanted||pending;$('stopCamera').disabled=!wanted&&!pending;}
  async function poll(){if(pollPending)return;pollPending=true;const e=epoch;try{const d=await api.get('camera/status');if(e!==epoch)return;supported=d.supported!==false;if(!supported)clear(d.error||'相机尚未接入');const now=performance.now();previewTimes=previewTimes.filter(t=>now-t<3000);const actual=wanted&&d.valid&&previewTimes.length>1?(previewTimes.length-1)*1000/(previewTimes[previewTimes.length-1]-previewTimes[0]):0;text('cameraMeta',(d.width||'—')+'×'+(d.height||'—')+' · 目标 '+(d.requested_fps||'—')+' 帧/秒 · 实际预览约 '+actual.toFixed(1)+' 帧/秒');if(wanted&&!pending&&!d.running){wanted=false;clear(d.error||'摄像头已停止');}if(wanted&&!pending&&!d.valid)clear(d.error||'没有新鲜画面');badge('cameraState',wanted?(d.valid?'画面更新中':'等待画面'):'画面未开启',wanted&&d.valid?'online':'');availability(Boolean(wanted&&d.valid));buttons();}catch(error){if(e===epoch){availability(false);if(wanted)clear('画面连接中断');badge('cameraState','服务未连接','bad');}}finally{pollPending=false;}}
  async function frame(){if(!wanted||pending||framePending||document.hidden||performance.now()-lastFetch<period)return;framePending=true;lastFetch=performance.now();const e=epoch;try{const d=await api.image('camera/frame');if(e!==epoch||!wanted)return;if(d.seq===seq)return;seq=d.seq;const next=URL.createObjectURL(d.blob),old=url;url=next;$('cameraImage').src=next;$('cameraImage').hidden=false;$('cameraPlaceholder').hidden=true;if(old)URL.revokeObjectURL(old);}catch(error){if(e===epoch&&wanted)clear('等待新画面，请检查相机链路');}finally{framePending=false;}}
  async function start(restart=false){
    if(pending||document.hidden)return;wanted=true;pending=true;const e=++epoch;const choice={resolution:$('cameraResolution').value,fps:Number($('cameraFps').value)};const resume=restart&&recording.isActive(),intent=recording.getIntent();buttons();availability(false);clear(restart?'正在切换清晰度与帧率…':'正在开启外接摄像头…');
    try{
      if(restart){if(resume)await recording.stop(false);if(e!==epoch||!wanted)return;await api.post('camera/stop',{},7000);}
      if(e!==epoch||!wanted)return;
      await api.post('camera/start',choice,7000);
      if(e!==epoch||!wanted||document.hidden){await api.post('camera/stop',{},7000);return;}
      period=1000/choice.fps;seq=null;previewTimes=[];lastFetch=0;
      if(resume){let valid=false;const until=performance.now()+5000;while(performance.now()<until&&e===epoch&&wanted&&!document.hidden){const d=await api.get('camera/status');if(d.valid){valid=true;break;}await new Promise(r=>setTimeout(r,100));}if(valid&&e===epoch&&wanted&&!document.hidden&&intent===recording.getIntent())await recording.start(true);else text('recordMessage','切换后未续录；请检查画面并手动开始。');}
    }catch(error){if(e===epoch){wanted=false;clear(error.message);badge('cameraState','摄像头未就绪','bad');}}
    finally{pending=false;buttons();poll();if(wanted&&(choice.resolution!==$('cameraResolution').value||choice.fps!==Number($('cameraFps').value)))choiceChanged();}
  }
  function choiceChanged(){clearTimeout(choiceTimer);if(!wanted)return;badge('cameraState','等待自动切换');choiceTimer=setTimeout(()=>{if(wanted&&!pending)start(true);},500);}
  async function stop(){epoch++;wanted=false;clearTimeout(choiceTimer);availability(false);clear('画面已关闭');buttons();try{await recording.stop();await api.post('camera/stop',{},7000);}catch(error){text('cameraMeta','关闭未确认：'+error.message);}finally{buttons();poll();}}
  $('startCamera').addEventListener('click',()=>start());$('stopCamera').addEventListener('click',stop);
  ['cameraResolution','cameraFps'].forEach(id=>$(id).addEventListener('change',choiceChanged));
  $('cameraImage').addEventListener('load',()=>{if(wanted)previewTimes.push(performance.now());});
  $('cameraImage').addEventListener('error',()=>{if(wanted)clear('画面解码失败');});
  const frames=setInterval(frame,16),status=setInterval(poll,1000);poll();
  function leave(){clearTimeout(choiceTimer);if(wanted||pending){epoch++;wanted=false;availability(false);clear('页面已进入后台，画面已关闭');api.beacon('camera/stop');}buttons();}
  return {stop,leave,destroy(){leave();clearInterval(frames);clearInterval(status);}};
}
