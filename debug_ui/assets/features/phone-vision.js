import {$,text,badge} from '../core/dom.js';

/** A separate result view; it never paints an old box onto a newer preview. */
export function createPhoneVision(api){
  let available=false,pending=false,enabled=true,lastGood=0,expiryTimer=null;
  const names={red:'红色',green:'绿色',blue:'蓝色'};
  const states={SEARCHING:'寻找目标',LOCKING:'正在锁定',TRACKING:'连续跟踪中',LOST:'目标丢失',STALE:'等待新鲜结果',PAUSED:'计算已暂停'};
  function clear(){
    $('phoneVisionDot').hidden=true;text('phoneVisionOffset','等待目标进入画面');
  }
  function render(d,transportMs=0){
    clearTimeout(expiryTimer);
    enabled=Boolean(d.enabled);$('phoneVisionToggle').textContent=enabled?'暂停计算':'恢复计算';
    if(document.activeElement!==$('phoneVisionMode')&&d.mode)$('phoneVisionMode').value=d.mode;
    const age=Number(d.source_age_ms)+transportMs;
    const fresh=d.valid&&d.source_age_ms>=0&&age<250;
    badge('phoneVisionState',states[fresh||d.state==='PAUSED'?d.state:'STALE']||'等待结果',fresh&&d.state==='TRACKING'?'online':'');
    if(fresh&&d.bbox&&Number.isFinite(d.error_x)&&Number.isFinite(d.error_y)){
      $('phoneVisionDot').hidden=false;$('phoneVisionDot').style.left=((d.error_x+1)*50)+'%';$('phoneVisionDot').style.top=((d.error_y+1)*50)+'%';
      text('phoneVisionOffset',(names[d.mode]||'目标')+' #'+d.track_id+' · 水平 '+d.error_x.toFixed(2)+' / 垂直 '+d.error_y.toFixed(2));
      expiryTimer=setTimeout(()=>{clear();badge('phoneVisionState','结果已过期','');},Math.max(0,250-age));
    }else clear();
    text('phoneVisionDetail',d.error?'本机算法：'+d.error:fresh?'本机处理 '+Number(d.processing_ms||0).toFixed(1)+' ms · 结果年龄约 '+Math.round(age)+' ms · 算法帧 '+d.frame_seq:'开启相机后，由小手机处理最新画面。');
  }
  async function poll(){
    if(!available||pending||document.hidden)return;pending=true;
    try{const started=performance.now(),d=await api.get('vision/status',1800);lastGood=performance.now();render(d,lastGood-started);}
    catch(error){clear();badge('phoneVisionState','服务未就绪','');text('phoneVisionDetail',error.message);}
    finally{pending=false;}
  }
  async function configure(active){
    try{render(await api.post('vision/config',{mode:$('phoneVisionMode').value,enabled:active}));}
    catch(error){text('phoneVisionDetail',error.message);}
  }
  $('phoneVisionMode').addEventListener('change',()=>configure(true));
  $('phoneVisionToggle').addEventListener('click',()=>configure(!enabled));
  const timer=setInterval(()=>{if(lastGood&&performance.now()-lastGood>1000){clear();badge('phoneVisionState','结果已过期','');}poll();},125);
  return {start(info){available=Boolean(info.local_vision);$('phoneVisionPanel').hidden=!available;if(available)poll();},leave(){clearTimeout(expiryTimer);clear();},destroy(){clearTimeout(expiryTimer);clearInterval(timer);}};
}
