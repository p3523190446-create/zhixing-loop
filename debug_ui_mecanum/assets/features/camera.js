import {$,text,badge} from '../core/dom.js';
/** Owns preview frames, automatic settings switching and recording continuation. */
export function createCamera(api, recording, availability) {
  let wanted=false,pending=false,stopping=false,epoch=0,stopEpoch=0,framePending=false,pollPending=false;
  let url=null,seq=null,period=1000/15,lastFetch=0,previewTimes=[],choiceTimer=null;
  function clear(message){$('cameraImage').hidden=true;$('cameraImage').removeAttribute('src');$('cameraPlaceholder').hidden=false;$('cameraPlaceholder').textContent=message;text('cameraFrameLabel','NO SIGNAL');text('cameraLiveMeta','等待视频源');if(url)URL.revokeObjectURL(url);url=null;}
  // Closing is a recovery operation, even when a failed response or a new page
  // does not yet know that the phone's shared camera service is running.
  function buttons(){$('startCamera').disabled=wanted||pending||stopping;$('stopCamera').disabled=stopping;}
  async function poll(){if(pollPending)return;pollPending=true;const e=epoch;try{const d=await api.get('camera/status');if(e!==epoch)return;for(const option of $('cameraResolution').options)option.disabled=Boolean(d.native_only)&&option.value!=='160x120';for(const option of $('cameraFps').options)option.disabled=Boolean(d.native_only)&&option.value!=='5';if(d.native_only&&!wanted&&!pending&&!stopping){$('cameraResolution').value='160x120';$('cameraFps').value='5';}if(!pending&&!stopping){const wasWanted=wanted;wanted=Boolean(d.running);if(wanted&&d.requested_fps>0)period=1000/d.requested_fps;if(wanted&&!wasWanted){seq=null;lastFetch=0;previewTimes=[];}if(!wanted||!d.valid)clear(d.error||(wanted?'等待第一帧':'摄像头已停止'));}const now=performance.now();previewTimes=previewTimes.filter(t=>now-t<3000);const actual=wanted&&d.valid&&previewTimes.length>1?(previewTimes.length-1)*1000/(previewTimes[previewTimes.length-1]-previewTimes[0]):0;text('cameraMeta',(d.width||'—')+'×'+(d.height||'—')+' · 目标 '+(d.requested_fps||'—')+' 帧/秒 · 实际预览约 '+actual.toFixed(1)+' 帧/秒');if(d.mode_fallback)text('cameraMeta',$('cameraMeta').textContent+' · 相机不提供'+d.requested_resolution+'，使用实际输入尺寸');if(d.negotiated_fps>0&&d.negotiated_fps!==d.requested_fps)text('cameraMeta',$('cameraMeta').textContent+' · 相机输入 '+d.negotiated_fps+' 帧/秒');if(d.native_only)text('cameraMeta',$('cameraMeta').textContent+' · 主控转发');badge('cameraState',wanted?(d.valid?'画面更新中':'等待画面'):'画面未开启',wanted&&d.valid?'online':'');availability(Boolean(wanted&&d.valid));buttons();}catch(error){if(e===epoch){availability(false);if(wanted)clear('画面连接中断');badge('cameraState','服务未连接','bad');}}finally{pollPending=false;}}
  async function frame(){if(!wanted||pending||framePending||document.hidden||performance.now()-lastFetch<period)return;framePending=true;lastFetch=performance.now();const e=epoch;try{const d=await api.image('camera/frame');if(e!==epoch||!wanted)return;if(d.seq===seq)return;seq=d.seq;const next=URL.createObjectURL(d.blob),old=url;url=next;$('cameraImage').src=next;$('cameraImage').hidden=false;$('cameraPlaceholder').hidden=true;if(old)URL.revokeObjectURL(old);}catch(error){if(e===epoch&&wanted)clear('等待新画面，请检查相机链路');}finally{framePending=false;}}
  async function start(restart=false){
    if(pending||stopping||document.hidden)return;wanted=true;pending=true;const e=++epoch,stopAtStart=stopEpoch;const choice={resolution:$('cameraResolution').value,fps:Number($('cameraFps').value)};const resume=restart&&recording.isActive(),intent=recording.getIntent();buttons();availability(false);clear(restart?'正在切换清晰度与帧率…':'正在开启外接摄像头…');
    try{
      if(restart){if(resume)await recording.stop(false);if(e!==epoch||!wanted)return;await api.post('camera/stop',{},7000);}
      if(e!==epoch||!wanted)return;
      await api.post('camera/start',choice,7000);
      if(stopAtStart!==stopEpoch){await api.post('camera/stop',{},7000);return;}
      if(e!==epoch||!wanted)return;
      period=1000/choice.fps;seq=null;previewTimes=[];lastFetch=0;
      if(resume){let valid=false;const until=performance.now()+5000;while(performance.now()<until&&e===epoch&&wanted&&!document.hidden){const d=await api.get('camera/status');if(d.valid){valid=true;break;}await new Promise(r=>setTimeout(r,100));}if(valid&&e===epoch&&wanted&&!document.hidden&&intent===recording.getIntent())await recording.start(true);else text('recordMessage','切换后未续录；请检查画面并手动开始。');}
    }catch(error){if(e===epoch){wanted=false;clear(error.message);badge('cameraState','摄像头未就绪','bad');}}
    finally{pending=false;buttons();poll();if(wanted&&(choice.resolution!==$('cameraResolution').value||choice.fps!==Number($('cameraFps').value)))choiceChanged();}
  }
  function choiceChanged(){clearTimeout(choiceTimer);if(!wanted)return;badge('cameraState','等待自动切换');choiceTimer=setTimeout(()=>{if(wanted&&!pending)start(true);},500);}
  async function stop(){if(stopping)return;epoch++;stopEpoch++;wanted=false;stopping=true;clearTimeout(choiceTimer);availability(false);clear('正在关闭画面…');buttons();try{await api.post('camera/stop',{},7000);clear('画面已关闭');try{await recording.stop();}catch(error){text('recordMessage','记录保存状态待核对：'+error.message);}}catch(error){text('cameraMeta','关闭未确认：'+error.message);clear('关闭未确认，可再次点击关闭画面');}finally{stopping=false;buttons();poll();}}
  $('startCamera').addEventListener('click',()=>start());$('stopCamera').addEventListener('click',stop);
  ['cameraResolution','cameraFps'].forEach(id=>$(id).addEventListener('change',choiceChanged));
  $('cameraImage').addEventListener('load',()=>{
    if(!wanted)return;
    previewTimes.push(performance.now());
    const image=$('cameraImage'),width=image.naturalWidth,height=image.naturalHeight;
    if(width>0&&height>0)image.parentElement.style.setProperty('--camera-aspect',width+' / '+height);
    text('cameraFrameLabel','FRAME '+String(seq==null?'—':seq).padStart(5,'0'));
    const times=previewTimes.filter(t=>performance.now()-t<3000);
    const fps=times.length>1?(times.length-1)*1000/(times[times.length-1]-times[0]):0;
    text('cameraLiveMeta',width+' × '+height+' · 预览 '+fps.toFixed(1)+' FPS');
  });
  $('cameraImage').addEventListener('error',()=>{if(wanted)clear('画面解码失败');});
  const frames=setInterval(frame,16),status=setInterval(poll,1000);poll();
  // The camera belongs to the phone service, not to a particular browser page.
  // Permission dialogs and an observing iPad leaving must not close that stream.
  function leave(){clearTimeout(choiceTimer);epoch++;wanted=false;availability(false);clear('返回页面后同步手机摄像头状态');buttons();}
  buttons();
  return {stop,leave,destroy(){leave();clearInterval(frames);clearInterval(status);}};
}
