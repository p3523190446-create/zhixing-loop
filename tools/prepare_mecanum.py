"""Prepare an isolated mecanum variant. No device access or firmware writes."""
from pathlib import Path
import hashlib, json, shutil

ROOT = Path(__file__).resolve().parents[2]
SW = ROOT / '知行回路软件'
BASE = SW / 'build/r1_imu_observer/source-snapshot'
OVERLAY = SW / 'board/r1_mecanum'
UI = SW / 'debug_ui_mecanum'

def replace(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)

def main():
    OVERLAY.mkdir(exist_ok=True)
    # Do not overwrite an already prepared variant or another agent's edits.
    s = (BASE / 'wheel_control.c').read_text(encoding='utf-8')
    s = replace(s, 'uint32_t wheel_control_step(uint32_t now,int32_t left,int32_t right,const volatile int32_t speeds[4])',
                'uint32_t wheel_control_step4(uint32_t now,const int32_t inputs[4],const volatile int32_t speeds[4])')
    s = replace(s, '    if(left < -250 || left > 250 || right < -250 || right > 250)return fault(65);',
                '    for(i=0;i<4;i++)if(inputs[i]<-250||inputs[i]>250)return fault(65);')
    s = replace(s, 'input=i<2?left:right', 'input=inputs[i]')
    s += '\nuint32_t wheel_control_step(uint32_t now,int32_t left,int32_t right,const volatile int32_t speeds[4])\n{int32_t inputs[4]={left,left,right,right};return wheel_control_step4(now,inputs,speeds);}\n'
    (OVERLAY / 'wheel_control.c').write_text(s, encoding='utf-8')
    s = (BASE / 'wheel_control.h').read_text(encoding='utf-8')
    s = replace(s, '#endif', 'uint32_t wheel_control_step4(uint32_t now,const int32_t inputs[4],const volatile int32_t speeds[4]);\n#endif')
    (OVERLAY / 'wheel_control.h').write_text(s, encoding='utf-8')
    s = (BASE / 'remote_drive.c').read_text(encoding='utf-8')
    s = replace(s, '#include "wheel_control.h"', '#include "wheel_control.h"\n#include "mecanum_mix.h"')
    s = replace(s, 'static volatile int32_t desired_left,desired_right;',
                'static volatile int32_t desired_left,desired_right;\nstatic int32_t desired_wheels[4];\nstatic int32_t desired_forward,desired_strafe,desired_turn;')
    s = replace(s, '    desired_left=desired_right=0;dirty=0u;reason=why;',
                '    desired_left=desired_right=desired_forward=desired_strafe=desired_turn=0;\n    memset(desired_wheels,0,sizeof(desired_wheels));dirty=0u;reason=why;')
    s = replace(s, 'wheel_control_step(now,desired_left,desired_right,motor_speed_values)',
                'wheel_control_step4(now,desired_wheels,motor_speed_values)')
    s = replace(s, 'R1_DRIVE_STARTUP_MANUAL_V8_20261023', 'R1_DRIVE_STARTUP_MANUAL_MECANUM_V1_20261026')
    s = replace(s, 'DRIVE_CAPS,4,250,600', 'DRIVE_CAPS,5,250,600')
    s = replace(s, '    if(!strcmp(command,"DRIVE_STATUS")){', '''    if(!strcmp(command,"DRIVE_CHASSIS")){reply("DRIVE_CHASSIS,MECANUM_X,FL_RL_FR_RR,250,600\\n");return 1;}
    if(!strcmp(command,"DRIVE_VECTOR_STATUS")){
        snprintf(output,sizeof(output),"DRIVE_VECTOR,%ld,%ld,%ld,%ld,%ld,%ld,%ld\\n",
          (long)desired_forward,(long)desired_strafe,(long)desired_turn,
          (long)desired_wheels[0],(long)desired_wheels[1],(long)desired_wheels[2],(long)desired_wheels[3]);
        reply(output);return 1;
    }
    if(!strcmp(command,"DRIVE_STATUS")){''')
    s = replace(s, '        desired_left=desired_right=0;dirty=0;reason=0;sequence=0;last_set=now;',
                '        desired_left=desired_right=desired_forward=desired_strafe=desired_turn=0;\n        memset(desired_wheels,0,sizeof(desired_wheels));dirty=0;reason=0;sequence=0;last_set=now;')
    s = replace(s, '    if(!strncmp(command,"DRIVE_SET,",10)||!strncmp(command,"DRIVE_BRAKE,",12)){', '''    if(!strncmp(command,"DRIVE_VECTOR,",13)){
        int32_t forward,strafe,turn,targets[4];cursor=command+13;
        if(!unsigned_number(&cursor,&gen,',')||!unsigned_number(&cursor,&seq,',')||
           !pwm_number(&cursor,&forward,',')||!pwm_number(&cursor,&strafe,',')||
           !pwm_number(&cursor,&turn,0))goto invalid;
        if(!remote_drive_armed||gen!=generation||seq<=sequence||!seq)goto invalid;
        why=blocked(now);if(why){remote_drive_stop(why);goto invalid;}
        if(!mecanum_mix(forward,strafe,turn,targets))goto invalid;
        sequence=seq;desired_forward=forward;desired_strafe=strafe;desired_turn=turn;
        memcpy(desired_wheels,targets,sizeof(targets));
        desired_left=targets[0];desired_right=targets[2];last_set=now;reason=0;
        remote_drive_moving=forward!=0||strafe!=0||turn!=0;dirty=1;
        reply("DRIVE_VECTOR_ACCEPTED\\n");return 1;
    }
    /* Legacy two-side commands are deliberately rejected by this capability. */
    if(!strncmp(command,"DRIVE_BRAKE,",12)){''')
    s = replace(s, '        sequence=seq;desired_left=left;desired_right=right;last_set=now;reason=0;',
                '        sequence=seq;desired_left=left;desired_right=right;\n        desired_forward=desired_strafe=desired_turn=0;memset(desired_wheels,0,sizeof(desired_wheels));\n        last_set=now;reason=0;')
    (OVERLAY / 'remote_drive.c').write_text(s, encoding='utf-8')
    if not UI.exists():
        shutil.copytree(SW / 'debug_ui', UI, ignore=shutil.ignore_patterns('__pycache__','*.log','*-events.jsonl','runtime.json','demo-runtime.json'))
    for name in ('AndroidManifest.xml','BoardReplyException.java','DriveBroker.java','TelemetryService.java','GatewayService.java'):
        shutil.copy2(SW/'debug_ui/android'/name,UI/'android'/name)
    # Versioned variant keeps current live source and installed APK untouched.
    p=UI/'android/AndroidManifest.xml';s=p.read_text(encoding='utf-8').replace('versionCode="25"','versionCode="26"').replace('versionName="0.25"','versionName="0.26"');p.write_text(s,encoding='utf-8')
    p=UI/'android/BoardReplyException.java';s=p.read_text(encoding='utf-8').replace('command.startsWith("DRIVE_SET,")','command.startsWith("DRIVE_SET,")||command.startsWith("DRIVE_VECTOR,")');p.write_text(s,encoding='utf-8')
    p=UI/'android/DriveBroker.java';s=p.read_text(encoding='utf-8')
    s=replace(s, 'private String owner;', 'private volatile boolean mecanum;\n  public synchronized void setMecanum(boolean enabled){if(owner!=null)throw new IllegalStateException("请先停止行驶");mecanum=enabled;}\n  private String owner;')
    s=replace(s, '.put("protocol_version",2)', '.put("protocol_version",mecanum?5:2).put("chassis",mecanum?"mecanum":"differential")')
    s=replace(s, 'integer(body,"limit",1,100);}', 'integer(body,"limit",1,100);if(body.has("strafe"))integer(body,"strafe",-100,100);if(!mecanum&&body.optInt("strafe",0)!=0)throw new IllegalArgumentException("当前固件不支持横移");}')
    old='''      issued=true;exact(link,"DRIVE_SET,"+generation+","+next+","+nextLeft+","+nextRight,"DRIVE_SET_ACCEPTED");'''
    new='''      int strafe=job.body.has("strafe")?(int)integer(job.body,"strafe",-100,100):0;
      if(!mecanum&&strafe!=0)throw new IllegalArgumentException("当前固件不支持横移");
      if(mecanum){
        // Scale all axes together BEFORE MCU mixing; respect the selected speed ceiling.
        double norm=Math.max(100,Math.abs(throttle)+Math.abs(strafe)+Math.abs(turn));
        int f=(int)(throttle/norm*250*limit/100),x=(int)(strafe/norm*250*limit/100),z=(int)(turn/norm*250*limit/100);
        issued=true;exact(link,"DRIVE_VECTOR,"+generation+","+next+","+f+","+x+","+z,"DRIVE_VECTOR_ACCEPTED");
        nextLeft=f+x+z;nextRight=f-x-z;
      }else{issued=true;exact(link,"DRIVE_SET,"+generation+","+next+","+nextLeft+","+nextRight,"DRIVE_SET_ACCEPTED");}'''
    s=replace(s,old,new);p.write_text(s,encoding='utf-8')
    p=UI/'android/TelemetryService.java';s=p.read_text(encoding='utf-8')
    s=replace(s,'private volatile boolean lineCapable;','private volatile boolean lineCapable,driveMecanum;\n    public boolean driveMecanum(){return driveMecanum;}')
    s=replace(s,'.put("protocol_version",driveFullSpeed?4:driveNative?3:2)', '.put("protocol_version",driveMecanum?5:driveFullSpeed?4:driveNative?3:2).put("chassis",driveMecanum?"mecanum":"differential")')
    s=s.replace('driveCapable=false;driveManual=false;driveNative=false;driveProfileVerified=false;driveFullSpeed=false;driveSpeedLimit=0;',
                'driveCapable=false;driveManual=false;driveNative=false;driveProfileVerified=false;driveFullSpeed=false;driveSpeedLimit=0;driveMecanum=false;driveControls.disconnect();driveControls.setMecanum(false);')
    s=replace(s,'driveFullSpeed=driveCaps.equals("DRIVE_CAPS,4,250,600");', 'driveMecanum=driveCaps.equals("DRIVE_CAPS,5,250,600");\n                if(driveMecanum&&!query(conn,output,"DRIVE_CHASSIS","DRIVE_CHASSIS,").equals("DRIVE_CHASSIS,MECANUM_X,FL_RL_FR_RR,250,600"))throw new IOException("麦轮布局协议不符");\n                driveControls.setMecanum(driveMecanum);\n                driveFullSpeed=driveMecanum||driveCaps.equals("DRIVE_CAPS,4,250,600");')
    s=replace(s,'if(driveId.startsWith("DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_")){', 'if(driveMecanum&&!driveId.equals("DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_MECANUM_V1_20261026,1"))throw new IOException("麦轮固件标识不符");\n                if(driveId.startsWith("DRIVE_ID,R1_DRIVE_STARTUP_MANUAL_")){')
    p.write_text(s,encoding='utf-8')
    p=UI/'android/GatewayService.java';s=p.read_text(encoding='utf-8')
    s=replace(s,'    if(current!=null&&current.driveNative()){', '    data.getJSONObject("capabilities").put("mecanum_control",current!=null&&current.driveMecanum()&&current.manualDriveAvailable());\n    if(current!=null&&current.driveNative()){');p.write_text(s,encoding='utf-8')
    manifest={str(p.relative_to(SW)):hashlib.sha256(p.read_bytes()).hexdigest() for p in BASE.rglob('*') if p.is_file()}
    (OVERLAY/'baseline-sha256.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Isolated firmware and Android variant prepared')

if __name__=='__main__':main()
