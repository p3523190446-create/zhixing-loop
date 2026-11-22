import './core/view-gestures.js';
import {createApi} from './core/api.js';
import {createDrive} from './features/drive.js';
const $=id=>document.getElementById(id),api=createApi(),drive=createDrive(api);
let current=null,running=false,runUntil=0;
const field=(object,key,fallback)=>object&&object[key]!=null?object[key]:fallback;
function limit(){const value=Number($('driveLimit').value);$('limitHint').textContent=current&&current.control_model==='driver_native_speed'?`官方编码器速度闭环：满杆目标 ${current.capabilities&&current.capabilities.driver_speed_limit>120?Math.max(60,Math.round(current.capabilities.driver_speed_limit*value/100)):20+value}，当前速度上限${current.capabilities&&current.capabilities.driver_speed_limit||120}；左右按比例差速，可反向转弯。协议速度范围±1000；实际PWM未回报。`:`满杆目标 ${80+Math.floor(value*.4)}（驱动速度单位）；转弯内侧按比例减速。PWM命令不代表实际功率。`;}
$('driveLimit').addEventListener('input',limit);
document.querySelectorAll('[data-limit]').forEach(button=>button.addEventListener('click',()=>{
  $('driveLimit').value=button.dataset.limit;$('driveLimit').dispatchEvent(new Event('input'));limit();
}));
function benchButtons(){document.querySelectorAll('[data-run]').forEach(b=>b.disabled=!(current&&current.connected)||!$('benchConfirmed').checked||Boolean(current&&current.drive&&current.drive.active)||(current&&current.motor_active)||Boolean((current&&current.uart_errors))||Boolean((current&&current.uart_drops))||running||Date.now()<runUntil);if((current&&current.uart_errors)||(current&&current.uart_drops))$('benchFeedback').textContent=`固件拒绝固定单轮检查：累计串口错误 ${current.uart_errors}，丢字节 ${current.uart_drops}。保留日志后排查，不能跳过保护。`;}
$('benchConfirmed').addEventListener('change',benchButtons);
document.querySelectorAll('[data-run]').forEach(button=>button.addEventListener('click',async()=>{
  if(button.disabled)return;running=true;benchButtons();
  try{const d=await api.post('bench/run',{bench_confirmed:$('benchConfirmed').checked,channel:Number(button.dataset.run)},1800);runUntil=Date.now()+d.duration_ms+3000;$('benchFeedback').textContent=`M${d.channel} 单轮检查已启动，375PWM起转0.3秒后转250PWM；2.2秒后归零，再等3秒。此操作仅转一轮。`;}
  catch(error){$('benchFeedback').textContent=error.message;}
  finally{running=false;benchButtons();}
}));
function clearFeedback(){for(const id of ['voltage','distance','leftPwm','rightPwm','wheel1','wheel2','wheel3','wheel4','pwm1','pwm2','pwm3','pwm4'])$(id).textContent='—';}
async function update(){const version=drive.version();
  try{const data=await api.get('status',1800);current=data;limit();drive.render(data,version);
    $('linkState').textContent=data.connected?'P9主控已连接 · 真实数据':'主控未连接 · '+(data.error||'数据已过期');
    if(data.connected){$('voltage').textContent=data.voltage_mv==null?'—':(data.voltage_mv/1000).toFixed(2)+' V';$('distance').textContent=data.range_valid?data.distance_mm+' mm':'测距无效（不拦截）';$('leftPwm').textContent=field(data.speed_targets,0,'—');$('rightPwm').textContent=field(data.speed_targets,2,'—');for(let i=1;i<=4;i++){$('wheel'+i).textContent=field(data.wheel_speeds,i-1,'—');$('pwm'+i).textContent=data.control_model==='driver_native_speed'?field(data.speed_commands,i-1,'—')+' 速度命令':(field(data.applied_pwm,i-1,'—'))+' PWM';}const reasons={0:'允许手动拍摄遥控；测距只提示',2:'旧固件测距拦截，请核对更新',4:'驱动电压、反馈或串口检查未通过',8:'官方TT配置尚未读取或不匹配',6:'单轮测试正在进行'};const f=data.controller_fault||0;$('guardState').textContent=f?'控制器已停机：'+(f<=4?`M${f}持续没有转动反馈，请检查后重新开启`:f<=20?`M${f-16}速度过高`:f<=36?`M${f-32}反馈方向异常`:`M${f-48}反向前未停稳`):'主控检查：'+(reasons[data.blocked]||'原因 '+data.blocked);}
    else{clearFeedback();$('guardState').textContent='未连接时不发送运动指令';}
  }catch(error){current=null;clearFeedback();drive.render({connected:false,capabilities:{}},version);$('linkState').textContent=error.message;}
  benchButtons();
}
let polling=false;setInterval(async()=>{if(polling)return;polling=true;try{await update();}finally{polling=false;}},300);
addEventListener('pagehide',()=>api.beacon('drive/stop'));document.addEventListener('visibilitychange',()=>{if(document.hidden){drive.leave();api.beacon('drive/stop');}});
limit();update();
