import {$, all, text, badge, number, duration} from '../core/dom.js';
const guards = ['安全距离','进入预警距离','进入危险距离','测距故障'];
const faults = ['无已锁存故障','轮速异常','轮速持续异常','编码器速度异常','反馈中断','串口错误','转动方向异常','其他车轮异常转动'];
export function createTelemetry(chart) {
  let lastSample = null;
  const metric = (name,value) => all('[data-metric="'+name+'"]').forEach(node => node.textContent=value);
  function render(data) {
    const live = Boolean(data.connected && data.link_age_ms != null && data.link_age_ms < 3000);
    const fresh = live && data.age_ms != null && data.age_ms < 5000;
    const valid = fresh && data.range_valid && data.distance_mm != null;
    const ultra = data.ultrasonic;
    const ultraValid = fresh && ultra && ultra.valid && ultra.age_ms != null && ultra.age_ms < 2000;
    badge('connection',live?'主控已连接':'主控未连接',live?'online':'bad');
    metric('distance',valid?number(data.distance_mm/10):'—');
    metric('ultra',ultraValid?number(ultra.distance_mm/10):'—');
    metric('voltage',fresh?number(data.voltage_mv==null?null:data.voltage_mv/1000,2):'—');
    metric('warning',fresh?number(data.warning_mm==null?null:data.warning_mm/10):'—');
    text('guard',valid?(guards[data.guard_state]||'状态未知'):'无有效新鲜读数');
    text('ultraNote',ultraValid?'主控超声回传 · 精度待校准':'无有效新鲜读数');
    text('sound',fresh&&data.muted!=null?(data.muted?'静音':'声音开启'):'声音状态未知');
    text('uptime',fresh?duration(data.uptime_s):'—');
    for(let i=0;i<4;i++)text('m'+(i+1),fresh&&data.wheel_speeds_mm_s?number(data.wheel_speeds_mm_s[i],0):'—');
    text('driver',fresh?(['未连接','待机','转动','故障'][data.driver_state]||'状态未知'):'—');
    text('fault',fresh?(faults[data.motor_fault]||'未知故障'):'—');
    text('uart',fresh?'错误 '+number(data.uart_errors,0)+' / 丢字节 '+number(data.uart_drops,0):'—');
    text('fresh',fresh?(data.age_ms/1000).toFixed(1)+' 秒前':'数据已中断或过期');
    let message=!live?(data.error||'连接中断，数值已清空。等待主控，不会自动开启动作。'):!fresh?'主控链路在线，但整组遥测已过期。':!valid?'原测距当前无有效数据；超声波单独显示。':data.driver_state===0?'当前仅调试云台，车辆运动禁用，暂无电机反馈。':data.guard_state===3?'主控报告测距故障。':null;
    $('notice').hidden=!message;text('notice',message||'');
    const sample=data.received_at||String(data.uptime_s);
    if(!fresh){chart.gap();lastSample=null;}else if(sample!==lastSample){chart.push(valid?data.distance_mm:null);lastSample=sample;}
    return {live,fresh};
  }
  return {render};
}
