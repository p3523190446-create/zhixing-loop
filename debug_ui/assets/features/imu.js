import {renderObserver} from './imu-observer.js';
export function imuView(data){
  const p=data&&data.mpu;
  const valid=Boolean(data&&data.connected&&p&&p.valid&&Number.isFinite(p.age_ms)&&p.age_ms>=0&&p.age_ms<1500&&
    Number.isFinite(p.front_up_deg)&&Number.isFinite(p.left_up_deg));
  return {valid,front:valid?p.front_up_deg:null,left:valid?p.left_up_deg:null,age:valid?p.age_ms:null,
    nonstandard:Boolean(p&&p.nonstandard_identity),identity:p&&p.identity,reference:Boolean(p&&p.reference_matches),
    compatPending:Boolean(data&&data.connected&&p&&!p.valid&&p.identity===114&&p.last_error===4)};
}
export function createImuView(api){
  const root=document.getElementById('imuCard');if(!root)return {render(){}};
  let seen=false;
  const compat=document.getElementById('imuCompatEnable'),feedback=document.getElementById('imuCompatFeedback');let enabling=false;
  if(compat&&api)compat.addEventListener('click',async()=>{if(enabling||compat.disabled)return;enabling=true;compat.disabled=true;feedback.hidden=false;feedback.textContent='正在等待主控兼容采集回执…';try{const reply=await api.post('mpu/compat',{enable:true,identity:114},3000);feedback.textContent=reply.message;}catch(error){feedback.textContent='未开启：'+error.message;}finally{enabling=false;}});
  function render(data){
    renderObserver(data);
    if(data&&data.mpu)seen=true;root.hidden=false;
    if(root.parentElement.classList.contains('sensor-deck'))root.parentElement.classList.toggle('has-imu',true);
    const view=imuView(data),label=document.getElementById('imuState');
    if(compat){compat.hidden=!(data&&data.connected&&data.capabilities&&data.capabilities.mpu_compatibility&&view.compatPending);compat.disabled=enabling;}
    root.setAttribute('data-status',view.valid?'live':view.compatPending?'attention':'offline');
    label.textContent=view.valid?(view.nonstandard?'兼容采集中':'实时采集中'):view.compatPending?'等待兼容采集':data&&!data.connected?'主控未连接':data&&data.mpu&&data.mpu.supported===false?'未提供姿态数据':'等待数据';
    for(const [key,value] of [['Front',view.front],['Left',view.left]]){
      document.getElementById('imu'+key+'Angle').textContent=value===null?'—':(value>=0?'+':'')+value.toFixed(1)+'°';
      const direction=value===null?'等待新鲜数据':Math.abs(value)<.5?'接近水平':
        key==='Front'?(value>0?'车头高':'车尾高'):(value>0?'左侧高':'右侧高');
      document.getElementById('imu'+key+'Direction').textContent=direction;
      const bar=document.getElementById('imu'+key+'Bar');bar.hidden=value===null;
      bar.style.transform='translate(-50%,-50%) rotate('+(value===null?0:-Math.max(-45,Math.min(45,value)))+'deg)';
    }
    document.getElementById('imuAge').textContent=view.valid?'更新于 '+Math.round(view.age)+' ms 前':view.compatPending?'等待主控恢复本车兼容采集':'等待有效数据，旧角度已清空';
    document.getElementById('imuDetail').textContent=view.identity==null?'等待传感器状态':
      '身份寄存器 0x'+view.identity.toString(16).toUpperCase()+' · '+(view.reference?'已载入本次水平参考':'尚无匹配的水平参考')+
      (view.identity===114?'。本车使用0x72兼容采集，配套主控上电后自动恢复。':view.nonstandard?'。身份与本车已保存参考不同。':'。');
  }
  return {render};
}
