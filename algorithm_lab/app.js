const $=id=>document.getElementById(id);
let labels=[],mode='preview',lastFrame=null,previewStarted=false;
let focusSourceValid=false,focusFrameSeq=null,focusLastSampleSeq=null,focusSourceKey='',focusPeak=0,focusSamples=[];
const names={red:'红色',green:'绿色',blue:'蓝色'};
const lineNames={offline:'数据失效',no_line:'未见黑线',all_black:'全部为黑',junction:'岔路 / 宽黑区',line:'单条黑线'};
function hideFrame(){
  $('frame').hidden=true;$('empty').hidden=false;
  if(previewStarted){$('frame').removeAttribute('src');previewStarted=false;}
  lastFrame=null;
  focusSourceValid=false;
  if($('focusROI'))$('focusROI').hidden=true;
}
function clearVision(d){
  ['colors','tags','motion'].forEach(id=>$(id).textContent='—');
  $('objects').textContent=d&&d.model_ready?'模型已加载，等待新鲜识别结果':d&&d.model_load_error?'模型加载失败：'+d.model_load_error:'等待新鲜识别结果';
  $('tagInfo').textContent='AprilTag 36h11';$('colorInfo').textContent='等待新鲜目标';
}
function selectMode(value){
  mode=value;hideFrame();
  $('previewButton').setAttribute('aria-pressed',value==='preview'?'true':'false');
  $('detectionButton').setAttribute('aria-pressed',value==='detection'?'true':'false');
}
$('previewButton').onclick=()=>selectMode('preview');
$('detectionButton').onclick=()=>selectMode('detection');
$('frame').onerror=()=>{previewStarted=false;lastFrame=null;};
function renderVideo(d){
  const camera=d.camera_source||{};
  const previewOK=camera.running&&camera.valid&&camera.age_ms<1500;
  const detectionOK=d.vision_valid&&d.vision;
  const fps=camera.observed_fps;
  focusSourceValid=!!previewOK;focusFrameSeq=camera.seq;
  const focusKey=(camera.source||'')+' '+(camera.resolution||'');
  if(focusSourceKey!==focusKey){focusSourceKey=focusKey;resetFocus();}
  $('focusROI').hidden=!(mode==='preview'&&previewOK);
  $('frameStatus').textContent=(camera.resolution||'—')+' · 预览 '+(fps===null||fps===undefined?'—':fps)+' fps · 识别 '+(d.detection_fps||'—')+' fps';
  if(mode==='preview'&&previewOK){
    $('frame').alt=(camera.source||'外接摄像头')+'实时预览';
    $('empty').hidden=true;$('frame').hidden=false;
    if(!previewStarted){$('frame').src='/preview.mjpeg?t='+Date.now();previewStarted=true;}
  }else if(mode==='detection'&&detectionOK){
    $('frame').alt='模型处理过的对应画面';
    $('empty').hidden=true;$('frame').hidden=false;
    if(!previewStarted){$('frame').src='/detection.mjpeg?t='+Date.now();previewStarted=true;}
  }else{hideFrame();$('empty').textContent=mode==='preview'?'等待摄像头画面':'等待新鲜识别结果';}
}
function render(d){
  $('error').textContent=d.error||d.vision_wait||'';
  const l=d.line;
  $('lineState').textContent=l?lineNames[l.state]:'等待数据';
  $('channels').textContent='';
  if(l&&l.dark)l.dark.forEach((dark,i)=>{
    const node=document.createElement('div');node.className='channel'+(dark?' dark':'');node.textContent='X'+(i+1);$('channels').append(node);
  });
  $('dot').hidden=!(l&&l.position!==null);
  if(l&&l.position!==null)$('dot').style.left=((l.position+1)*50)+'%';
  $('lineCorrection').textContent=l&&l.correction!==null?'偏移 '+l.position.toFixed(2)+' · 纠偏建议 '+l.correction.toFixed(2):'当前不给出纠偏建议';
  const telemetry=d.telemetry||{};
  $('board').textContent=d.connected?'主控在线':'主控离线';
  const imu=telemetry.mpu;
  $('imu').textContent=imu&&imu.valid?'车头高 '+imu.front_up_deg.toFixed(1)+'° / 车左高 '+imu.left_up_deg.toFixed(1)+'°':'姿态无有效读数；非标准身份兼容采样未启用';
  $('record').textContent=(d.recording_samples||0)+' 组'+(d.recording_active?' · 采集中':' · 已结束');
  renderVideo(d);
  const tracker=d.tracking||{};
  const trackNames={SEARCHING:'寻找目标',LOCKING:'正在锁定',TRACKING:'连续跟踪中',LOST:'目标丢失',STALE:'画面过期',PAUSED:'跟踪已暂停'};
  $('trackingState').textContent=trackNames[tracker.state]||'等待目标';
  $('trackingToggle').textContent=tracker.enabled?'暂停跟踪计算':'开始跟踪计算';
  if(document.activeElement!==$('trackingMode')&&tracker.mode)$('trackingMode').value=tracker.mode;
  $('trackingOffset').textContent=tracker.error_x===null||tracker.error_x===undefined?'等待目标进入画面':
    '目标 #'+tracker.track_id+' · 水平 '+tracker.error_x.toFixed(2)+' / 垂直 '+tracker.error_y.toFixed(2);
  $('trackingRequest').textContent=d.vision&&d.vision.face_error?'人脸分支：'+d.vision.face_error:tracker.pointing_request?
    '修正请求 X '+tracker.pointing_request.image_x.toFixed(2)+' / Y '+tracker.pointing_request.image_y.toFixed(2):'当前没有云台修正请求';
  if(d.model_backend==='onnxruntime_cuda')$('frameStatus').textContent+=' · 显卡推理';
  if(d.vision_valid&&d.vision){
    const v=d.vision;
    $('objects').textContent=v.model_error?'模型错误：'+v.model_error:v.objects.length?v.objects.map(o=>(labels[o.class_id]||('类别 '+o.class_id))+' '+Math.round(o.score*100)+'%').join(' · '):'本帧未检测到超过 45% 阈值的物体';
    const c=v.colors[0];
    $('colors').textContent=c?names[c.color]:'未见色块';
    $('colorInfo').textContent=c?'水平偏移 '+c.offset_x.toFixed(2)+' / 垂直偏移 '+c.offset_y.toFixed(2):'等待明显的红 / 绿 / 蓝目标';
    $('tags').textContent=v.tags.length?v.tags.map(t=>'#'+t.id).join(' / '):'未见路标';
    $('tagInfo').textContent='连续 '+v.tag_confirmation_frames+' 帧 · 未判定到站';
    $('motion').textContent=v.motion_fraction===null?'等待比较':Math.round(v.motion_fraction*100)+'% 变化';
  }else clearVision(d);
  $('raw').textContent=JSON.stringify({camera:d.camera_source,line:d.line,vision:d.vision,source_age_ms:d.source_age_ms,odometry:d.odometry,actuation_enabled:d.actuation_enabled},null,2);
}
async function poll(){
  try{
    const response=await fetch('/api/status',{cache:'no-store'});
    if(!response.ok)throw Error('服务不可达');
    render(await response.json());
  }catch(error){
    hideFrame();clearVision();$('board').textContent='连接中断';$('lineState').textContent='数据失效';
    $('channels').textContent='';$('dot').hidden=true;$('lineCorrection').textContent='';$('imu').textContent='—';$('error').textContent=String(error);
    $('trackingState').textContent='数据失效';$('trackingOffset').textContent='—';$('trackingRequest').textContent='当前没有云台修正请求';
  }
  setTimeout(poll,100);
}
async function configureTracking(enabled){
  try{
    const response=await fetch('/api/tracking/config',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({mode:$('trackingMode').value,enabled})});
    if(!response.ok)throw Error('跟踪设置未接受');
  }catch(error){$('error').textContent=String(error);}
}
$('trackingMode').onchange=()=>configureTracking(true);
$('trackingToggle').onclick=()=>configureTracking($('trackingToggle').textContent==='开始跟踪计算');
let previousEvents='';
async function pollEvents(){
  try{
    const events=await (await fetch('/api/events',{cache:'no-store'})).json();
    const ids=events.map(e=>e.id).join(',');
    if(ids!==previousEvents){
      previousEvents=ids;$('eventList').textContent='';
      const names={target_acquired:'目标锁定',target_lost:'目标丢失',tracking_ended:'跟踪结束',marker_seen:'看到路标',scene_changed:'画面变化'};
      events.slice(0,6).forEach(event=>{
        const link=document.createElement('a');link.href='/events/'+event.id+'.jpg';link.target='_blank';link.rel='noopener';
        const image=document.createElement('img');image.src=link.href;image.alt=names[event.reason]||'事件照片';image.loading='lazy';
        const title=document.createElement('span');title.textContent=(names[event.reason]||'事件')+' · '+event.at.slice(11,19);
        link.append(image,title);$('eventList').append(link);
      });
      $('eventCount').textContent=events.length?'最近 '+events.length+' 条':'等待目标、路标或画面变化';
    }
  }catch(error){}
  setTimeout(pollEvents,1000);
}
fetch('/labels').then(r=>r.json()).then(d=>labels=d).catch(()=>{});
poll();pollEvents();

// Sample only the raw preview. Detection overlays would artificially add edges.
const focusCanvas=document.createElement('canvas');focusCanvas.width=320;focusCanvas.height=240;
const focusContext=focusCanvas.getContext('2d',{willReadFrequently:true});
function resetFocus(){
  focusPeak=0;focusSamples=[];focusLastSampleSeq=null;
  $('focusPeak').textContent='—';$('focusCurrent').textContent='—';$('focusBar').style.width='0%';
}
function focusVariance(rgba,width,height){
  const gray=new Float32Array(width*height);
  for(let p=0,i=0;p<gray.length;p++,i+=4)gray[p]=.299*rgba[i]+.587*rgba[i+1]+.114*rgba[i+2];
  let sum=0,squared=0,count=0;
  for(let y=1;y<height-1;y++)for(let x=1;x<width-1;x++){
    const p=y*width+x,v=gray[p-width]+gray[p+width]+gray[p-1]+gray[p+1]-4*gray[p];
    sum+=v;squared+=v*v;count++;
  }
  return Math.max(0,squared/count-(sum/count)**2);
}
function sampleFocus(){
  try{
    const image=$('frame');
    if(!focusSourceValid||image.hidden||!image.naturalWidth||mode!=='preview'){
      $('focusCurrent').textContent='—';$('focusBar').style.width='0%';
      $('focusHint').textContent=mode!=='preview'?'切回“流畅预览”后计算清晰度，避免检测框影响分数。':'等待新鲜相机画面';
      focusSamples=[];return;
    }
    if(focusFrameSeq===focusLastSampleSeq)return;
    focusLastSampleSeq=focusFrameSeq;
    focusContext.drawImage(image,image.naturalWidth*.25,image.naturalHeight*.25,image.naturalWidth*.5,image.naturalHeight*.5,0,0,320,240);
    const pixels=focusContext.getImageData(0,0,320,240).data;
    const score=focusVariance(pixels,320,240);
    focusSamples.push(score);if(focusSamples.length>3)focusSamples.shift();
    const ordered=focusSamples.slice().sort((a,b)=>a-b),current=ordered[Math.floor(ordered.length/2)];
    focusPeak=Math.max(focusPeak,current);
    const ratio=focusPeak>0?Math.min(1,current/focusPeak):0;
    $('focusCurrent').textContent=current.toFixed(1);$('focusPeak').textContent=focusPeak.toFixed(1);
    $('focusBar').style.width=(ratio*100).toFixed(1)+'%';
    $('focusHint').textContent=current<.5?'中心框细节很少：请对准有文字、纹理或清楚边缘的物体。':
      '当前为本次最高值的 '+Math.round(ratio*100)+'% · 保持同一场景，缓慢转动对焦环比较。';
  }catch(error){$('focusHint').textContent='清晰度暂时不可读：'+String(error);}
  finally{setTimeout(sampleFocus,150);}
}
$('focusReset').onclick=resetFocus;
$('focusExpand').onclick=()=>{
  selectMode('preview');document.body.classList.toggle('focus-mode');
  $('focusExpand').textContent=document.body.classList.contains('focus-mode')?'返回算法面板':'放大对焦画面';
};
sampleFocus();
