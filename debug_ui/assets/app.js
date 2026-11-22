import './core/view-gestures.js';
import {createApi} from './core/api.js?v=0287';
import {createRealtime} from './core/realtime.js';
import {createNavigation} from './features/navigation.js';
import {createDistanceChart} from './features/chart.js';
import {createTelemetry} from './features/telemetry.js';
import {createLineView} from './features/line.js';
import {createLineCalibration} from './features/line-calibration.js';
import {createLineTaskPlan} from './features/line-task-plan.js';
import {createImuView} from './features/imu.js?v=0283';
import {createDiagnostics} from './features/diagnostics.js';
import {createGimbal} from './features/gimbal.js?v=0286';
import {createDrive} from './features/drive.js';
import {createPhotos} from './features/photos.js';
import {createCamera} from './features/camera.js';
import {createPhoneVision} from './features/phone-vision.js';
import {createGimbalFollow} from './features/gimbal-follow.js?v=0290';
import {createLargeVision} from './features/large-vision.js?v=0272';
import {createRecording} from './features/recording.js';
import {createReplay} from './features/replay.js';
import {createControlLayout} from './features/control-layout.js';
import {$} from './core/dom.js';

const api=createApi(),chart=createDistanceChart(),telemetry=createTelemetry(chart),diagnostics=createDiagnostics();
const line=createLineView();
const lineCalibration=createLineCalibration(api);
const lineTask=createLineTaskPlan(api);
const imu=createImuView(api);
// Keep the verified HTTP path by default. The realtime preview is explicit opt-in.
const realtimeRequested=new URLSearchParams(location.search).get('transport')==='ws';
const drive=createDrive(api),photos=createPhotos(api),gimbal=createGimbal(api),recording=createRecording(api),replay=createReplay(api);
// Hiding an entire control module also releases its control lease.
$('driveCard').addEventListener('toggle',()=>{if(!$('driveCard').open)drive.leave();});
$('gimbalCard').addEventListener('toggle',()=>{if(!$('gimbalCard').open){gimbal.leave();gimbalFollow.leave();}});
const controlLayout=createControlLayout({drive,gimbal});
let cameraReady=false,controllerReady=false,polling=false,lastSuccess=0,realtime=null,statusGeneration=0;
const camera=createCamera(api,recording,value=>{cameraReady=value;recording.setReady(cameraReady);photos.setReady(cameraReady);});
const phoneVision=createPhoneVision(api);
const gimbalFollow=createGimbalFollow(api,gimbal);
const largeVision=createLargeVision(api);
createNavigation(tab=>{if(tab==='telemetry')requestAnimationFrame(chart.draw);if(tab==='live')requestAnimationFrame(controlLayout.refresh);if(tab!=='records')replay.pause();if(tab!=='live'){drive.leave();gimbal.leave();gimbalFollow.leave();lineTask.leave();}});
function render(data, version=gimbal.version(), driveVersion=drive.version(),taskVersion=lineTask.version()){const state=telemetry.render(data);line.render(data);lineCalibration.render(data);imu.render(data);controllerReady=state.fresh;recording.setReady(cameraReady);gimbal.render(data,version);drive.render(data,driveVersion);diagnostics.render(data);lineTask.render(data,taskVersion);$('sourceAge').textContent=data.age_ms==null||data.age_ms<0?'—':Math.round(data.age_ms)+' ms';}
async function update(){if(polling||document.hidden||realtime&&realtime.active())return;polling=true;const version=gimbal.version(),driveVersion=drive.version(),taskVersion=lineTask.version(),generation=statusGeneration;try{const data=await api.get('status',2500);if(generation!==statusGeneration||realtime&&realtime.active())return;lastSuccess=performance.now();render(data,version,driveVersion,taskVersion);}catch(error){if(generation===statusGeneration&&!(realtime&&realtime.active()))render({connected:false,error:error.message},version,driveVersion,taskVersion);}finally{polling=false;}}
api.get('ui/info').then(info=>{
  lineCalibration.start(info);
  phoneVision.start(info);
  gimbalFollow.start(info);
  gimbal.startSettings(info);
  $('demoNotice').hidden=!info.demo;
  if(realtimeRequested&&info.realtime&&info.realtime.websocket){
    realtime=createRealtime({base:api.base,
      onStatus(data){statusGeneration++;lastSuccess=performance.now();render(data);},
      onMode(value){$('transportMode').textContent=value;},
      onLatency(value){$('networkRtt').textContent=value?value.rtt_ms.toFixed(1)+' ms · P95 '+value.p95_ms.toFixed(1)+' ms ('+value.samples+'次)':'—';},
      onFailure(message){statusGeneration++;render({connected:false,error:message});}
    });api.attachRealtime(realtime);realtime.start();
  }
}).catch(()=>{});
const pollTimer=setInterval(update,1000),staleTimer=setInterval(()=>{if(lastSuccess&&performance.now()-lastSuccess>3000)render({connected:false,error:'服务回复已过期，控制需要重新开启。'});},500);
function leave(){lineTask.leave();drive.leave();gimbal.leave();gimbalFollow.leave();recording.leave();camera.leave();phoneVision.leave();largeVision.leave();replay.pause();if(realtime)realtime.suspend();}
document.addEventListener('visibilitychange',()=>{if(document.hidden)leave();else{if(realtime)realtime.resume();update();}});
addEventListener('pagehide',leave);update();
document.documentElement.setAttribute('data-ui-ready','true');
