export function observerView(data){
  const p=data&&data.mpu,f=p&&p.features;
  const valid=Boolean(data&&data.connected&&p&&p.valid&&f&&f.valid&&Number.isFinite(f.age_ms)&&f.age_ms>=0&&f.age_ms<1500);
  const states=valid&&Array.isArray(f.states)?f.states:[];
  const metric=(key,digits=3)=>valid&&Number.isFinite(f[key])?f[key].toFixed(digits):'—';
  const notices=[['freefall','失重候选'],['extreme_tilt','大幅倾斜'],['tilt','持续倾斜'],['shock_recent','突然冲击候选'],['rotating','正在转动'],['accelerating','横向加速，暂停颠簸评价']].filter(([key])=>states.includes(key)).map(([,label])=>label);
  let status=valid?(notices.join(' · ')||(states.includes('low_dynamic')?'低动态，当前变化较小':'正在观察')):
    f&&!f.reference_matches?'水平参考版本不匹配，算法数据停用':f?'算法数据无效或已过期':'等待板端算法';
  if(f&&!valid&&f.flags&128)status='原始量程饱和，算法数据停用';
  if(f&&!valid&&f.flags&256)status='连续原始数据不变，需检查传感器';
  return {valid,status,rms:metric('vibration_rms'),peak:metric('vibration_peak'),turn:metric('turn_window_deg',1),
    events:valid?`冲击 ${f.shock_count} · 倾斜 ${f.tilt_count} · 失重 ${f.freefall_count}`:'事件计数 —',
    window:valid&&!states.includes('window_ready')?'颠簸窗口准备中；转动、加速时暂停评价':'约 2 秒观察窗 · 数值相对已保存的静态重力'};
}
export function renderObserver(data){
  const root=document.getElementById('imuObserver');if(!root)return;
  const view=observerView(data);root.hidden=!(data&&data.mpu&&data.mpu.features);
  for(const [id,key] of [['imuRms','rms'],['imuPeak','peak'],['imuTurn','turn'],['imuMotion','status'],['imuEvents','events'],['imuWindow','window']])document.getElementById(id).textContent=view[key];
}
