"""Derive capability-gated controls from the retained original dashboard."""
from prepare_mecanum import SW,UI,replace

def main():
    p=UI/'android/TelemetryService.java';s=p.read_text(encoding='utf-8').replace('driveMecanum=false;driveControls.setMecanum(false);','driveMecanum=false;driveControls.disconnect();driveControls.setMecanum(false);');p.write_text(s,encoding='utf-8')
    p=UI/'index.html';s=(SW/'debug_ui/index.html').read_text(encoding='utf-8')
    s=replace(s,'class="stick-label west">左转','id="driveWestLabel" class="stick-label west">左转')
    s=replace(s,'class="stick-label east">右转','id="driveEastLabel" class="stick-label east">右转')
    s=replace(s,'<p class="hint">按住行驶，松手归零</p></div>', '<p class="hint" id="driveInputHint">按住行驶，松手归零</p><div class="button-row" data-mecanum-only hidden><button class="button secondary" data-drive-direction="rotateLeft" disabled>原地左转</button><button class="button secondary" data-drive-direction="rotateRight" disabled>原地右转</button></div></div>')
    s=replace(s,'40%</output><input id="driveLimit" type="range" min="10" max="100" step="5" value="40"','20%</output><input id="driveLimit" type="range" min="10" max="100" step="5" value="20"')
    s=s.replace('左侧速度目标','左前速度目标').replace('右侧速度目标','右前速度目标')
    p.write_text(s,encoding='utf-8')
    p=UI/'assets/features/drive.js';s=(SW/'debug_ui/assets/features/drive.js').read_text(encoding='utf-8')
    s=replace(s,'let throttle=0,turn=0,sequence=0','let mecanum=false,strafe=0;\n  let throttle=0,turn=0,sequence=0')
    s=replace(s,'(50+turn*.36)', '(50+(mecanum?strafe:turn)*.36)')
    s=replace(s,"text('driveTarget',`前后 ${throttle} / 转向 ${turn}`);", "text('driveTarget',mecanum?`前后 ${throttle} / 横移 ${strafe} / 旋转 ${turn}`:`前后 ${throttle} / 转向 ${turn}`);")
    s=replace(s,'throttle=turn=0;paint();','throttle=turn=strafe=0;paint();')
    s=replace(s,"outputs[i]+(nativeModel?' 速度命令':' PWM')", "outputs[i]+(nativeModel?' 速度命令':' PWM')+(mecanum&&targets[i]!=null?' / 目标 '+targets[i]:'')")
    s=replace(s,"    nativeModel=data.control_model==='driver_native_speed';", """    const nextMecanum=Boolean(data.capabilities&&data.capabilities.mecanum_control);
    if(nextMecanum!==mecanum&&session)leave();
    mecanum=nextMecanum;
    text('driveWestLabel',mecanum?'左移':'左转');text('driveEastLabel',mecanum?'右移':'右转');
    text('driveInputHint',mecanum?'摇杆控制平移，按钮控制旋转；方向键平移，Q / E旋转，松手归零':'按住行驶，松手归零');
    all('[data-mecanum-only]').forEach(el=>el.hidden=!mecanum);
    const labels=mecanum?{left:'左移',right:'右移',forwardLeft:'左前斜移',forwardRight:'右前斜移',backLeft:'左后斜移',backRight:'右后斜移'}:{left:'原地左转',right:'原地右转',forwardLeft:'前进左拐',forwardRight:'前进右拐',backLeft:'倒车左转',backRight:'倒车右转'};
    all('[data-drive-direction]').forEach(b=>{if(labels[b.dataset.driveDirection])b.textContent=labels[b.dataset.driveDirection];});
    nativeModel=data.control_model==='driver_native_speed';""")
    s=replace(s,'  function target(forward,steer){','  function target(forward,steer,rotation=0){')
    s=replace(s,'    throttle=dead(forward);turn=dead(steer);paint();','    throttle=dead(forward);strafe=mecanum?dead(steer):0;turn=mecanum?dead(rotation):dead(steer);paint();')
    s=replace(s,"turn:forceZero?0:turn,limit:Number($('driveLimit').value)};", "turn:forceZero?0:turn,strafe:forceZero?0:strafe,limit:Number($('driveLimit').value)};")
    s=replace(s,"function keyTarget(){holding=keys.size>0;target((keys.has('ArrowUp')?100:0)-(keys.has('ArrowDown')?100:0),(keys.has('ArrowRight')?100:0)-(keys.has('ArrowLeft')?100:0));}", "function keyTarget(){holding=keys.size>0;target((keys.has('ArrowUp')?100:0)-(keys.has('ArrowDown')?100:0),(keys.has('ArrowRight')?100:0)-(keys.has('ArrowLeft')?100:0),mecanum?((keys.has('e')?100:0)-(keys.has('q')?100:0)):0);}")
    s=s.replace("['ArrowUp','ArrowDown','ArrowLeft','ArrowRight',' ']", "['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','q','e',' ']")
    s=replace(s,'if(!session||event.button>0||event.isPrimary===false)return;', 'if(!session||pointer!==null||event.button>0||event.isPrimary===false)return;')
    s=replace(s,'event.preventDefault();holding=true;button.setPointerCapture(event.pointerId);', 'event.preventDefault();pointer=event.pointerId;holding=true;button.setPointerCapture(event.pointerId);')
    s=replace(s,'      target(...directions[button.dataset.driveDirection]);send();', '''      if(mecanum){
        Object.assign(directions,{forwardLeft:[100,-100],forwardRight:[100,100],backLeft:[-100,-100],backRight:[-100,100],rotateLeft:[0,0,-100],rotateRight:[0,0,100]});
      }
      const v=directions[button.dataset.driveDirection];if(v){target(...v);send();}''')
    s=replace(s,"name,()=>{if(holding)release();}","name,event=>{if(holding&&event.pointerId===pointer)release();}")
    s=replace(s,"    paint();\n  }\n  function leave()", "    if(mecanum){text('driveSpeedHint','麦轮：平移和旋转合成四轮独立目标；当前档位 '+$('driveLimit').value+'%，单位沿用驱动回报，尚未实车验收。');}\n    paint();\n  }\n  function leave()")
    p.write_text(s,encoding='utf-8')
    print('Mecanum controls prepared')

if __name__=='__main__':main()
