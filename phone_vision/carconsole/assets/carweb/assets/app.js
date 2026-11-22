import {createApi} from './core/api.js';
import {createNavigation} from './features/navigation.js';
import {createDistanceChart} from './features/chart.js';
import {createTelemetry} from './features/telemetry.js';
import {createDiagnostics} from './features/diagnostics.js';
import {createGimbal} from './features/gimbal.js';
import {createCamera} from './features/camera.js';
import {createRecording} from './features/recording.js';
import {createReplay} from './features/replay.js';
import {$} from './core/dom.js';

const api=createApi(),chart=createDistanceChart(),telemetry=createTelemetry(chart),diagnostics=createDiagnostics();
const gimbal=createGimbal(api),recording=createRecording(api),replay=createReplay(api);
let cameraReady=false,controllerReady=false,polling=false,lastSuccess=0;
const camera=createCamera(api,recording,value=>{cameraReady=value;recording.setReady(true);});
createNavigation(tab=>{if(tab==='telemetry')requestAnimationFrame(chart.draw);if(tab!=='records')replay.pause();});
function render(data, version=gimbal.version()){const state=telemetry.render(data);controllerReady=state.fresh;recording.setReady(true);gimbal.render(data,version);diagnostics.render(data);}
async function update(){if(polling||document.hidden)return;polling=true;const version=gimbal.version();try{const data=await api.get('status',2500);lastSuccess=performance.now();render(data,version);}catch(error){render({connected:false,error:error.message},version);}finally{polling=false;}}
api.get('ui/info').then(info=>{$('demoNotice').hidden=!info.demo;recording.setReady(true);}).catch(()=>{});
const pollTimer=setInterval(update,1000),staleTimer=setInterval(()=>{if(lastSuccess&&performance.now()-lastSuccess>3000)render({connected:false,error:'服务回复已过期，控制需要重新开启。'});},500);
function leave(){gimbal.leave();recording.leave();camera.leave();replay.pause();}
document.addEventListener('visibilitychange',()=>{if(document.hidden)leave();else update();});
addEventListener('pagehide',leave);update();
