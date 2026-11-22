"""Replace only the drive card; retain camera, line calibration and diagnostics."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];UI=ROOT/'知行回路软件/debug_ui'

CARD='''        <details class="card control-card drive-card fold-card mecanum-station" id="driveCard" open>
          <summary class="module-summary"><div class="panel-name"><small>MOVE / TURN</small><h2 id="driveTitle">麦轮遥控</h2></div><span id="driveState" class="badge">等待主控</span><span class="fold-chevron" aria-hidden="true"></span></summary>
          <div class="module-body">
            <div class="drive-top-actions"><button id="startDrive" class="button" disabled>开启遥控</button><button id="stopDrive" class="button danger">停止并锁定</button></div>
            <div class="drive-reference"><span class="car-heading" aria-hidden="true">↑</span><span>以车头为前方</span><span class="reference-note">左边移动车身 · 右边改变朝向</span></div>
            <div id="drivePlanes" class="drive-planes">
              <section class="drive-zone move-zone" aria-label="平移控制">
                <div class="zone-heading"><span class="zone-number">01</span><h3 id="driveMoveTitle">平移</h3></div>
                <p id="driveMoveHint" class="zone-note">车头不转，朝推杆方向移动</p>
                <div class="stick-shell"><div id="driveJoystick" class="stick-pad drive-stick" role="group" aria-label="平移摇杆，向任意方向拖动，松手停止平移" aria-disabled="true" tabindex="0">
                  <span class="compass n">前进</span><span class="compass ne" data-mecanum-only>右前</span><span id="driveEastLabel" class="compass e">右移</span><span class="compass se" data-mecanum-only>右后</span><span class="compass s">后退</span><span class="compass sw" data-mecanum-only>左后</span><span id="driveWestLabel" class="compass w">左移</span><span class="compass nw" data-mecanum-only>左前</span>
                  <div class="stick-axis vertical"></div><div class="stick-axis horizontal"></div>
                  <div id="driveThumb" class="stick-thumb"><svg viewBox="0 0 30 38" aria-hidden="true"><path d="M15 3 24 14H6Z"/><rect x="8" y="16" width="14" height="17" rx="4"/></svg></div>
                </div></div>
                <p class="zone-footnote">轻推慢移 · 推远加速</p>
              </section>
              <section class="drive-zone spin-zone" data-mecanum-only aria-label="转向控制">
                <div class="zone-heading"><span class="zone-number">02</span><h3>转向</h3></div><p class="zone-note">改变车头朝向，也能原地转</p>
                <div class="stick-shell"><div id="driveTurnPad" class="stick-pad turn-stick" role="group" aria-label="转向摇杆，向左左转，向右右转，松手停止转向" aria-disabled="true" tabindex="0">
                  <span class="turn-mark ccw" aria-hidden="true">↶</span><span class="turn-mark cw" aria-hidden="true">↷</span><span class="turn-label left">左转</span><span class="turn-label right">右转</span><div class="turn-rail"></div>
                  <div id="driveTurnThumb" class="stick-thumb turn-thumb"><svg viewBox="0 0 30 38" aria-hidden="true"><path d="M15 3 24 14H6Z"/><rect x="8" y="16" width="14" height="17" rx="4"/></svg></div>
                </div></div>
                <div class="spin-buttons"><button class="button secondary" data-drive-direction="rotateLeft" disabled><span aria-hidden="true">↶</span><span class="direction-name">按住左转</span></button><button class="button secondary" data-drive-direction="rotateRight" disabled><span aria-hidden="true">↷</span><span class="direction-name">按住右转</span></button></div>
              </section>
            </div>
            <div class="drive-intent"><span id="driveMotionDot" class="motion-dot"></span><div><small>当前手势</small><strong id="driveIntent">先开启遥控，再按住摇杆</strong></div></div>
            <p id="driveInputHint" class="drive-use-note">左边平移，右边转向；可双指同时操作。全部松开，四轮归零。</p>
            <div id="driveFeedback" class="feedback" role="status">连接主控后可开启遥控。</div>
            <label class="drive-speed">速度档位 <output id="driveLimitValue">20%</output><input id="driveLimit" type="range" min="10" max="100" step="5" value="20"><span class="speed-endpoints"><span>慢</span><span>快</span></span></label>
            <details class="mecanum-help" data-mecanum-only><summary>侧移和转向，有什么区别？<span>看图理解</span></summary><div class="motion-lessons">
              <div><svg viewBox="0 0 140 82" aria-hidden="true"><g class="lesson-car"><rect x="49" y="27" width="42" height="44" rx="10"/><path d="m62 40 8-7 8 7"/><path d="M44 34v11m0 8v11m52-30v11m0 8v11"/></g><path class="lesson-arrow" d="M70 24V6m-7 7 7-7 7 7"/></svg><b>前进 / 后退</b><p>车头朝向不变，车身前后走。</p></div>
              <div><svg viewBox="0 0 140 82" aria-hidden="true"><g class="lesson-car"><rect x="27" y="21" width="42" height="49" rx="10"/><path d="m40 35 8-7 8 7"/><path d="M22 28v13m0 10v12m52-35v13m0 10v12"/></g><path class="lesson-arrow" d="M82 46h42m-8-8 8 8-8 8"/></svg><b>向右侧移</b><p>车头还朝前，整辆车向右挪。</p></div>
              <div><svg viewBox="0 0 140 82" aria-hidden="true"><g class="lesson-car"><rect x="49" y="26" width="42" height="45" rx="10"/><path d="m62 40 8-7 8 7"/></g><path class="lesson-spin" d="M33 45a37 32 0 0 1 71-9m-9-1 9 1 1-10"/></svg><b>原地转向</b><p>车身转动，车头换个方向。</p></div>
            </div><p class="wheel-explainer">轮子边缘的小滚子是斜着的。四个轮子搭配正反转，让某些方向的推力抵消、另一些方向的推力合起来，所以车身可以侧移。轮子本身不用像汽车前轮那样扭过去。</p><p class="wheel-explainer">摇杆可以连续选择任意平面方向，不只八个固定方向；右边还能同时控制转向。“保持朝向”这里指不主动转向，并不是已经实现了自动锁定角度。</p></details>
            <details id="driveButtons" class="fold-tools direction-tools"><summary>八方向按键<span class="fold-hint">按住移动</span></summary><div class="direction-grid">
              <button class="button secondary" data-drive-direction="forwardLeft" disabled><i>↖</i><span class="direction-name">左前</span></button><button class="button secondary" data-drive-direction="forward" disabled><i>↑</i><span class="direction-name">前进</span></button><button class="button secondary" data-drive-direction="forwardRight" disabled><i>↗</i><span class="direction-name">右前</span></button>
              <button class="button secondary" data-drive-direction="left" disabled><i>←</i><span class="direction-name">左移</span></button><button id="driveBrake" class="button brake-button" disabled><i>■</i><span>归零</span></button><button class="button secondary" data-drive-direction="right" disabled><i>→</i><span class="direction-name">右移</span></button>
              <button class="button secondary" data-drive-direction="backLeft" disabled><i>↙</i><span class="direction-name">左后</span></button><button class="button secondary" data-drive-direction="back" disabled><i>↓</i><span class="direction-name">后退</span></button><button class="button secondary" data-drive-direction="backRight" disabled><i>↘</i><span class="direction-name">右后</span></button>
            </div></details>
            <div class="drive-instruments"><div><span>前方距离</span><strong data-metric="distance">—</strong><small>cm</small></div><div><span>驱动电压</span><strong data-metric="voltage">—</strong><small>V</small></div></div>
            <details id="driveTools" class="fold-tools"><summary>控制反馈与键盘<span class="fold-hint">展开</span></summary><div class="fold-content">
              <p class="hint">方向键 / WASD：平移 · Q / E：转向 · 空格：停止并锁定。</p><p id="driveTarget" class="hint">当前零指令</p><p id="driveSpeedHint" class="hint">速度百分比不代表实测车速。</p>
              <div class="drive-instruments"><div><span>左前速度目标</span><strong id="driveSpeedLeft">—</strong></div><div><span>右前速度目标</span><strong id="driveSpeedRight">—</strong></div></div>
              <div class="drive-pwm-readout"><span>M1 <b id="driveOutputM1">—</b></span><span>M2 <b id="driveOutputM2">—</b></span><span>M3 <b id="driveOutputM3">—</b></span><span>M4 <b id="driveOutputM4">—</b></span></div><p id="driveControllerFault" class="hint">等待控制器反馈</p><p id="groundDriveReason" class="hint">当前只做过悬空检查，落地表现待验证。</p>
            </div></details>
          </div>
        </details>
'''
def main():
 p=UI/'index.html';s=p.read_text(encoding='utf-8-sig');start=s.index('        <details class="card control-card drive-card');end=s.index('        <details class="card control-card fold-card" id="gimbalCard"',start)
 s=s[:start]+CARD+s[end:]
 if 'assets/mecanum.css' not in s:s=s.replace('</head>','  <link rel="stylesheet" href="assets/mecanum.css">\n</head>')
 p.write_text(s,encoding='utf-8');print('Drive card redesigned in the existing project')
if __name__=='__main__':main()
