import {$} from '../core/dom.js';

/** One immutable picture per answer; the model has no drive/gimbal permissions. */
export function createLargeVision(api){
  const mount=document.getElementById('vlmMount')||document.getElementById('cameraCard');
  if(!mount)return {leave(){}};
  const panel=document.createElement('section');panel.className='large-vision-panel';panel.id='largeVisionPanel';
  panel.innerHTML=`<div class="card-heading"><div><h2>大模型看图</h2><p class="hint">Qwen3-VL · 电脑本地多模态大模型</p></div><span id="vlmState" class="badge">尚未连接</span></div>
    <label class="vlm-question">想了解画面中的什么？<textarea id="vlmQuestion" rows="2" maxlength="600">请描述画面中有哪些主要物体、颜色和相对位置；看不清的地方请明确说明。</textarea></label>
    <div class="button-row"><button type="button" id="vlmCapture" class="button">识别当前画面</button></div>
    <div id="vlmMessage" class="hint" role="status" aria-live="polite">先开启相机，再点识别。结果对应本次快照，不随预览自动更新。</div>
    <div id="vlmResult" class="vlm-result" hidden><img id="vlmImage" alt="本次送入大模型的原图"><div><p id="vlmProvenance" class="hint"></p><p id="vlmAnswer" class="vlm-answer"></p><p id="vlmMetrics" class="hint"></p><a id="vlmDownload" class="button secondary compact" download="知行回路-大模型识别.json" hidden>下载本次记录</a></div></div>
    <details id="vlmSettings" class="fold-tools"><summary>模型连接与照片分析<span class="fold-hint">展开</span></summary><div class="fold-content">
      <label>电脑模型服务地址<input id="vlmEndpoint" type="url" spellcheck="false" placeholder="http://电脑IP:8797/启动时显示的完整路径/"></label>
      <button id="vlmConnect" type="button" class="button secondary compact">连接模型服务</button>
      <label>也可选择一张照片<input id="vlmFile" type="file" accept="image/jpeg,image/png"></label><button id="vlmAnalyzeFile" type="button" class="button secondary compact">分析选中照片</button>
      <p class="hint">相机与车控仍在小手机上；这一项由电脑计算。照片分析会明确标为选中照片。</p>
    </div></details>`;
  if(mount.id==='cameraCard')mount.insertBefore(panel,document.getElementById('cameraTools'));else mount.appendChild(panel);
  let busy=false,epoch=0,timer=null,previewUrl=null,recordUrl=null,lastResult=null,connected=false,sharedSettings=false,relay=false;
  const sameOrigin=document.body.dataset.vlmSameOrigin==='true';
  let endpoint='';try{endpoint=localStorage.getItem('zhixing-vlm-endpoint')||'';}catch(ignored){}
  if(sameOrigin)endpoint=location.origin+api.base;
  $('vlmEndpoint').value=endpoint;
  function message(value){$('vlmMessage').textContent=value;}
  function state(value){$('vlmState').textContent=value;}
  function controls(){['vlmCapture','vlmAnalyzeFile'].forEach(id=>{$(id).disabled=busy||!connected;});$('vlmConnect').disabled=busy;}
  function bridgeBase(){
    const value=$('vlmEndpoint').value.trim();if(!value)throw new Error('请先连接电脑模型服务；在下方填写完整服务地址并点击连接。');
    let url;try{url=new URL(value);}catch(error){throw new Error('模型服务地址格式不正确，请填写完整HTTP地址。');}
    if(url.protocol!=='http:'||url.username||url.password||url.search||url.hash)throw new Error('请填写电脑模型服务的完整HTTP地址');
    return url.href.replace(/\/$/,'');
  }
  async function request(path,body){
    if(relay)return body?api.post('vlm/'+path,body,7000):api.get('vlm/'+path,7000);
    const abort=new AbortController(),timeout=setTimeout(()=>abort.abort(),6000);
    try{const response=await fetch(bridgeBase()+'/api/vlm/'+path,{method:body?'POST':'GET',cache:'no-store',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,signal:abort.signal});const data=await response.json();if(!response.ok)throw new Error(data.error||'模型服务未确认请求');return data;}
    catch(error){if(error.name==='AbortError')throw new Error('电脑模型服务连接超时，请检查地址和同一网络');throw error;}
    finally{clearTimeout(timeout);}
  }
  async function connect(){
    connected=false;controls();
    try{state('连接中');endpoint=bridgeBase();if(sharedSettings)await api.post('vlm/settings',{url:endpoint});const data=await request('status');if(!data.available)throw new Error(data.message);try{localStorage.setItem('zhixing-vlm-endpoint',endpoint);}catch(ignored){}connected=true;state('模型已连接');message(data.model+' · 电脑本地运行 · '+(relay?'由小手机统一转发':'直接连接模型服务')+' · 点击识别会拍一张快照');$('vlmSettings').open=false;}
    catch(error){state('未连接');message(error.message);$('vlmSettings').open=true;}finally{controls();}
  }
  function clearAnswer(){lastResult=null;$('vlmAnswer').textContent='';$('vlmMetrics').textContent='';$('vlmDownload').hidden=true;if(recordUrl)URL.revokeObjectURL(recordUrl);recordUrl=null;}
  function showPicture(blob,source,captured){
    if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=URL.createObjectURL(blob);$('vlmImage').src=previewUrl;$('vlmResult').hidden=false;
    $('vlmProvenance').textContent=(source==='camera_snapshot'?'本次相机快照':'手动选中照片')+' · '+new Date(captured).toLocaleString();
  }
  function base64(blob){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(new Error('图片读取失败'));reader.readAsDataURL(blob);});}
  async function poll(id,e,deadline){
    if(e!==epoch)return;
    try{
      const result=await request('job/'+encodeURIComponent(id));if(e!==epoch)return;
      if(result.state==='failed')throw new Error(result.error);
      if(result.state==='done'){
        lastResult=result;$('vlmAnswer').textContent=result.answer;
        $('vlmMetrics').textContent=result.model+' · 推理 '+(result.elapsed_ms/1000).toFixed(2)+' 秒 · 本次图片分析，未控制车辆';
        const age=Math.max(0,(Date.now()-Date.parse(result.captured_at))/1000);
        message('识别完成。这张图片距现在约 '+Math.round(age)+' 秒；回答不代表当前实时路况。');
        state('本次识别完成');recordUrl=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));$('vlmDownload').href=recordUrl;$('vlmDownload').hidden=false;busy=false;controls();return;
      }
      if(Date.now()>deadline)throw new Error('本次分析等待超时，请检查电脑服务；不展示旧回答');
      timer=setTimeout(()=>poll(id,e,deadline),650);
    }catch(error){if(e===epoch){state('本次未完成');message(error.message);busy=false;controls();}}
  }
  async function analyze(fileMode){
    if(busy)return;
    const e=++epoch;busy=true;controls();clearAnswer();state('正在取图');message('准备本次图片…');
    try{
      bridgeBase();let blob,seq='',source='selected_photo',captured=new Date().toISOString();
      if(fileMode){blob=$('vlmFile').files[0];if(!blob)throw new Error('请先选择一张JPEG或PNG照片');}
      else{
        const info=await api.get('ui/info');if(info.demo)throw new Error('模拟预览不能作为真实相机识别，请选择实际照片或连接车载网页');
        const start=performance.now(),camera=await api.get('camera/status');
        if(!camera.running||!camera.valid||camera.age_ms>2000)throw new Error('当前没有新鲜相机画面，请先开启并确认预览');
        const image=await api.image('camera/frame');if(image.unchanged||!image.blob)throw new Error('没有取得新快照');
        if(performance.now()-start>3000)throw new Error('取图耗时过长，请重试');
        blob=image.blob;seq=image.seq||String(camera.seq||'');source='camera_snapshot';captured=new Date().toISOString();
      }
      if(blob.size>2000000)throw new Error('图片超过2MB，请降低清晰度后重试');
      const encoded=await base64(blob);if(e!==epoch)return;
      showPicture(blob,source,captured);state('大模型分析中');message('正在分析这张快照，首次加载模型可能需要较长时间…');
      const result=await request('analyze',{image_base64:encoded,question:$('vlmQuestion').value.trim(),input_source:source,frame_seq:seq,captured_at:captured});
      if(e!==epoch)return;poll(result.id,e,Date.now()+175000);
    }catch(error){if(e===epoch){state('本次未完成');message(error.message);busy=false;controls();}}
  }
  $('vlmConnect').addEventListener('click',connect);$('vlmCapture').addEventListener('click',()=>analyze(false));$('vlmAnalyzeFile').addEventListener('click',()=>analyze(true));
  $('vlmEndpoint').addEventListener('input',()=>{connected=false;controls();});
  controls();
  api.get('ui/info').then(info=>{sharedSettings=Boolean(info.large_vision_settings);relay=Boolean(info.large_vision_relay);if(sharedSettings&&info.large_vision&&info.large_vision.url){endpoint=info.large_vision.url;$('vlmEndpoint').value=endpoint;}}).catch(()=>{}).then(()=>{if(endpoint)connect();else{state('先连接模型');message('请在下方连接电脑模型服务。连接后，各浏览器会自动读取车载App保存的地址。');$('vlmSettings').open=true;}});
  return {leave(){epoch++;clearTimeout(timer);busy=false;controls();if(!lastResult){state('已停止等待');message('已停止等待；返回后可重新取图分析。');}}};
}
