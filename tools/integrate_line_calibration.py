"""One-time source integration; no hardware commands."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def edit(rel,old,new):
 p=ROOT/rel;s=p.read_text(encoding='utf-8-sig')
 if new in s:return
 assert s.count(old)==1,(rel,old[:100]);p.write_text(s.replace(old,new),encoding='utf-8')
edit('debug_ui/android/TelemetryService.java','    private final LineTaskBroker lineTask=new LineTaskBroker();','''    private final LineTaskBroker lineTask=new LineTaskBroker();
    private LineCalibration calibration;
    private void initLineCalibration(){
      LineCalibration.Store store=json->{if(!getSharedPreferences("line_calibration",0).edit().putString("json",json).commit())throw new IOException("手机标定存储失败");};
      try{calibration=new LineCalibration(getSharedPreferences("line_calibration",0).getString("json",null),store);}catch(Exception error){android.util.Log.e("ZXR_DASH","Invalid line profile",error);try{calibration=new LineCalibration(null,store);}catch(Exception impossible){throw new IllegalStateException(impossible);}}
    }
    private boolean calibrationIdle()throws Exception{
      if(lineTask.active()||driveControls.publicState().optBoolean("active")||remoteControls.publicState().optBoolean("active"))return false;
      Map<String,String> rows=snapshot();String r=rows.get("DRIVE_STATUS"),g=rows.get("GIMBAL_STATUS");
      if(r==null||g==null)return false;String[] d=r.split(",",-1),p=g.split(",",-1);
      return d.length==10&&d[2].equals("0")&&d[3].equals("0")&&p.length==11&&p[3].equals("0");
    }
    public JSONObject lineCalibrationState()throws Exception{return calibration.state();}
    public JSONObject lineCalibrationCommand(String action)throws Exception{return calibration.command(action,calibrationIdle(),TelemetryCodec.decode(snapshot(),sampleAge(),busy,phase));}
''')
edit('debug_ui/android/TelemetryService.java','if(!manualDriveAvailable())throw new IOException','if(calibration.busy())throw new IOException("现场标定中，请先结束采样或保存");\n        if(!manualDriveAvailable())throw new IOException')
edit('debug_ui/android/TelemetryService.java','        return lineTask.submit(action,body);','        if(action.equals("start")&&(!calibration.ready()||calibration.busy()))throw new IOException("请先完成现场标定并核对主控参数");\n        return lineTask.submit(action,body);')
edit('debug_ui/android/TelemetryService.java','        remoteControls.pump(exchange);','        remoteControls.pump(exchange);\n        calibration.pump(exchange,calibrationIdle());')
edit('debug_ui/android/TelemetryService.java','        if(!gimbalAvailable())throw new IOException','        if(!action.equals("stop")&&calibration.busy())throw new IOException("现场标定中，请先结束采样或保存");\n        if(!gimbalAvailable())throw new IOException')
edit('debug_ui/android/TelemetryService.java','super.onCreate();initGimbalSettings();','super.onCreate();initGimbalSettings();initLineCalibration();')
edit('debug_ui/android/TelemetryService.java','            while(!cancelled){\n                long began=', '''            try{calibration.connect(exchange);}catch(Exception optional){event("line_calibration_unavailable","reason",optional.toString());}
            while(!cancelled){
                long began=''')
edit('debug_ui/android/TelemetryService.java','                event("sample_complete","cycle",samples,"fields",new JSONObject(cycle));','''                calibration.observe(TelemetryCodec.decode(cycle,0,true,phase),calibrationIdle());
                event("sample_complete","cycle",samples,"fields",new JSONObject(cycle));''')
edit('debug_ui/android/TelemetryService.java','            cancelled=true;cancelReader();','            calibration.disconnect();cancelled=true;cancelReader();')
edit('debug_ui/android/GatewayService.java','    data.put("line_task",current==null?', '    data.put("line_calibration",current==null?new JSONObject().put("supported",false).put("message","请先连接主控"):current.lineCalibrationState());\n    data.put("line_task",current==null?')
edit('debug_ui/android/GatewayService.java','    if(path.equals("gimbal/settings")){if(board==null)throw new IllegalStateException("主控服务未就绪");return board.gimbalSettings();}', '    if(path.equals("line-calibration/status")){if(board==null)throw new IllegalStateException("主控服务未就绪");return board.lineCalibrationState();}\n    if(path.equals("gimbal/settings")){if(board==null)throw new IllegalStateException("主控服务未就绪");return board.gimbalSettings();}')
edit('debug_ui/android/GatewayService.java','    if(path.startsWith("line-task/")){','    if(path.startsWith("line-calibration/")){if(board==null)throw new IllegalStateException("主控服务未就绪");return board.lineCalibrationCommand(path.substring(17));}\n    if(path.startsWith("line-task/")){')
edit('debug_ui/android/GatewayService.java','.put("local_vision",true).put("gimbal_calibration",true)','.put("line_calibration",true).put("local_vision",true).put("gimbal_calibration",true)')
edit('debug_ui/android/AndroidManifest.xml','android:versionName="0.25.4"','android:versionName="0.25.5"')
edit('debug_ui/index.html','        <details class="line-task-plan" id="lineTaskPlan">','''        <details class="line-calibration" id="lineCalibration" hidden open><summary>现场标定 · 手机独立完成 <span id="lineCalBadge">待标定</span></summary>
          <p class="line-cal-help">电机电池断开。保持实际离地高度，每次让整排八个探头对着同一种材料。无需电脑、无需抄数。</p>
          <ol class="line-cal-steps"><li id="lineCalFloorStep">无胶带地砖</li><li id="lineCalBlackStep">黑胶带</li><li id="lineCalSaveStep">保存并应用</li></ol>
          <div class="line-cal-actions"><button id="lineCalFloor" type="button" disabled>① 采地砖</button><button id="lineCalBlack" type="button" disabled>② 采黑胶带</button><button id="lineCalSave" type="button" disabled>③ 保存并应用</button></div>
          <p id="lineCalMessage" role="status">请先连接主控并开始记录。</p><progress id="lineCalProgress" max="6000" value="0" hidden></progress>
          <button id="lineCalCancel" type="button" hidden>取消本次采样</button>
          <small>采样约6秒；波动或反差不合格会提示重采。保存后重连主控会自动恢复；标定不会启动车轮。</small>
        </details>
        <details class="line-task-plan" id="lineTaskPlan">''')
edit('debug_ui/assets/app.js',"import {createLineView} from './features/line.js';","import {createLineView} from './features/line.js';\nimport {createLineCalibration} from './features/line-calibration.js';")
edit('debug_ui/assets/app.js','const line=createLineView();','const line=createLineView();\nconst lineCalibration=createLineCalibration(api);')
edit('debug_ui/assets/app.js','line.render(data);imu.render(data);','line.render(data);lineCalibration.render(data);imu.render(data);')
edit('debug_ui/assets/app.js','  phoneVision.start(info);','  lineCalibration.start(info);\n  phoneVision.start(info);')
edit('debug_ui/assets/features/line.js','  let count=0,segments=0,previous=false,total=0,weighted=0;','''  const profile=data.line_calibration&&data.line_calibration.ready&&data.line_calibration.profile;
  const calibrated=profile&&Array.isArray(profile.floor)&&Array.isArray(profile.black)&&profile.floor.length===8&&profile.black.length===8&&profile.floor.every((v,i)=>Number.isInteger(v)&&Number.isInteger(profile.black[i])&&v>=0&&profile.black[i]<=65535&&profile.black[i]-v>=300);
  let count=0,segments=0,previous=false,total=0,weighted=0;''')
edit('debug_ui/assets/features/line.js','    const dark=(p.digital_mask&(1<<i))===0;\n    const strength=Math.max(0,Math.min(1,(raw-white[i])/(black[i]-white[i])));','''    const dark=calibrated?raw-profile.floor[i]>=Math.ceil((profile.black[i]-profile.floor[i])/2):(p.digital_mask&(1<<i))===0;
    const strength=calibrated?Math.max(0,Math.min(1,(raw-profile.floor[i])/(profile.black[i]-profile.floor[i]))):data.line_calibration?(dark?1:0):Math.max(0,Math.min(1,(raw-white[i])/(black[i]-white[i])));''')
edit('debug_ui/assets/features/line.js',"(c.dark?'黑':'白')","(c.dark?'黑':'地面')")
edit('debug_ui/assets/features/line-task-plan.js','available=fresh&&t.available===true;','available=fresh&&t.available===true&&(!data.line_calibration||(data.line_calibration.ready&&!data.line_calibration.busy));')
print('Integrated phone calibration, dynamic MCU references, and actual UI')
