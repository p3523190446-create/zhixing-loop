import {renderObserver} from './imu-observer.js';
export function imuView(data){
  const p=data&&data.mpu;
  const valid=Boolean(data&&data.connected&&p&&p.valid&&Number.isFinite(p.age_ms)&&p.age_ms>=0&&p.age_ms<1500&&
    Number.isFinite(p.front_up_deg)&&Number.isFinite(p.left_up_deg));
  return {valid,front:valid?p.front_up_deg:null,left:valid?p.left_up_deg:null,age:valid?p.age_ms:null,
    nonstandard:Boolean(p&&p.nonstandard_identity),identity:p&&p.identity,reference:Boolean(p&&p.reference_matches),
    compatPending:Boolean(p&&!p.valid&&p.nonstandard_identity&&p.last_error===4)};
}
export function createImuView(){
  const root=document.getElementById('imuCard');if(!root)return {render(){}};
  let seen=false;
  function render(data){
    renderObserver(data);
    if(data&&data.mpu)seen=true;root.hidden=!seen;
    if(root.parentElement.classList.contains('sensor-deck'))root.parentElement.classList.toggle('has-imu',seen);
    const view=imuView(data),label=document.getElementById('imuState');
    root.setAttribute('data-status',view.valid?'live':view.compatPending?'attention':'offline');
    label.textContent=view.valid?(view.nonstandard?'兼容采集中':'实时采集中'):view.compatPending?'待兼容确认':'等待数据';
    for(const [key,value] of [['Front',view.front],['Left',view.left]]){
      document.getElementById('imu'+key+'Angle').textContent=value===null?'—':(value>=0?'+':'')+value.toFixed(1)+'°';
      const direction=value===null?'等待新鲜数据':Math.abs(value)<.5?'接近水平':
        key==='Front'?(value>0?'车头高':'车尾高'):(value>0?'左侧高':'右侧高');
      document.getElementById('imu'+key+'Direction').textContent=direction;
      const bar=document.getElementById('imu'+key+'Bar');bar.hidden=value===null;
      bar.style.transform='translate(-50%,-50%) rotate('+(value===null?0:-Math.max(-45,Math.min(45,value)))+'deg)';
    }
    document.getElementById('imuAge').textContent=view.valid?'更新于 '+Math.round(view.age)+' ms 前':view.compatPending?'兼容模式未开启，暂不显示角度':'等待有效数据，旧角度已清空';
    document.getElementById('imuDetail').textContent=view.identity==null?'等待传感器状态':
      '身份寄存器 0x'+view.identity.toString(16).toUpperCase()+' · '+(view.reference?'已载入本次水平参考':'尚无匹配的水平参考')+
      (view.nonstandard?'。芯片身份非标准，重启后兼容测试不会自动开启。':'。');
  }
  return {render};
}
