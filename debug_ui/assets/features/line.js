// Calibration from the actual stationary black/white captures on 2026-10-25.
// Position is in X1 -> X8 coordinates; no vehicle left/right assumption or actuation.
const white=[220,246,251,248,249,258,258,226];
const black=[3145,3452,3456,3414,3331,3352,3357,2969];
export function lineView(data){
  const p=data&&data.line;
  if(!data||!data.connected||!p||!p.valid||typeof p.age_ms!=='number'||p.age_ms<0||p.age_ms>=1500||
     !Array.isArray(p.raw)||p.raw.length!==8||p.raw.some(v=>typeof v!=='number'||!isFinite(v)||v<0||v>65535)||
     !Number.isInteger(p.digital_mask)||p.digital_mask<0||p.digital_mask>255)return {valid:false,channels:[],position:null,state:'offline'};
  const profile=data.line_calibration&&data.line_calibration.ready&&data.line_calibration.profile;
  const calibrated=profile&&Array.isArray(profile.floor)&&Array.isArray(profile.black)&&profile.floor.length===8&&profile.black.length===8&&profile.floor.every((v,i)=>Number.isInteger(v)&&Number.isInteger(profile.black[i])&&v>=0&&profile.black[i]<=65535&&profile.black[i]-v>=300);
  let count=0,segments=0,previous=false,total=0,weighted=0;
  const channels=p.raw.map((raw,i)=>{
    const dark=calibrated?raw-profile.floor[i]>=Math.ceil((profile.black[i]-profile.floor[i])/2):(p.digital_mask&(1<<i))===0;
    const strength=calibrated?Math.max(0,Math.min(1,(raw-profile.floor[i])/(profile.black[i]-profile.floor[i]))):data.line_calibration?(dark?1:0):Math.max(0,Math.min(1,(raw-white[i])/(black[i]-white[i])));
    if(dark){count++;if(!previous)segments++;const weight=Math.max(.01,strength);total+=weight;weighted+=weight*(2*i/7-1);}
    previous=dark;
    return {raw,dark,strength};
  });
  const state=count===0?'no_line':count===8?'all_black':segments>1?'multiple':'line';
  return {valid:true,channels,count,state,position:state==='line'?weighted/total:null,age_ms:p.age_ms};
}
export function createLineView(){
  const root=document.getElementById('lineCard');
  if(!root)return {render(){}};
  const badge=document.getElementById('lineState'),note=document.getElementById('linePosition');
  const marker=document.getElementById('lineMarker');
  const nodes=Array.from(root.querySelectorAll('[data-line-channel]'));
  function render(data){
    const view=lineView(data);
    root.setAttribute('data-status',view.valid?'live':'offline');
    const offset=document.getElementById('lineOffset'),count=document.getElementById('lineCount');
    if(offset)offset.textContent=view.position===null?'—':String(Math.round(Math.abs(view.position)*100));
    if(count)count.textContent=(view.valid?String(view.count):'—')+' / 8 路识黑';
    badge.textContent=view.valid?'数据更新中':'等待巡线数据';
    nodes.forEach((node,i)=>{
      const c=view.channels[i];node.classList.toggle('is-black',Boolean(c&&c.dark));
      node.classList.toggle('is-offline',!view.valid);
      node.querySelector('[data-line-value]').textContent=c?String(c.raw):'—';
      node.querySelector('[data-line-fill]').style.height=c?Math.round(c.strength*100)+'%':'0%';
      node.querySelector('[data-line-color]').textContent=c?(c.dark?'黑':'地面'):'—';
    });
    marker.hidden=view.position===null;
    if(view.position!==null){
      marker.style.left=((view.position+1)*50)+'%';
      note.textContent=Math.abs(view.position)<.12?'黑线接近中央':
        '黑线靠近 '+(view.position<0?'X1':'X8')+' 端 · 偏移 '+Math.round(Math.abs(view.position)*100)+'%';
    }else note.textContent=({offline:'等待新鲜数据',no_line:'未检测到黑线',all_black:'八路全部为黑色',multiple:'检测到多个黑色区域'})[view.state];
  }
  return {render};
}
