"""One bounded P9 gimbal command-path check after human confirms both servos unplugged."""
import argparse,datetime,json,time,urllib.request
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--servos-disconnected',action='store_true',required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parents[2]
out=root/'output/onboard_dashboard/gimbal-power-20261021';out.mkdir(exist_ok=True)
origin='http://127.0.0.1:8795';base=origin+'/-EkPeOg3Z3zePaJPwNnaX0fQ'
def get():
    with urllib.request.urlopen(base+'/api/status',timeout=2) as response:return json.load(response)
def post(area,body):
    request=urllib.request.Request(base+'/api/'+area,data=json.dumps(body).encode(),headers={'Origin':origin,'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=2) as response:return json.load(response)
result=dict(started=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    test='SAME_PC_P9_MANUAL_START_AND_KEEPALIVE_WITH_BOTH_SERVO_PLUGS_REMOVED',
    human_confirmed_servos_disconnected=True,samples=[],motion_hardware_connected=False)
failure=None;attempted=False
try:
    post('drive/stop',{});post('gimbal/stop',{})
    initial=get();result['initial']=initial
    if not initial['connected'] or initial['drive']['active'] or initial['motor_active'] or initial['gimbal']['active']:raise RuntimeError('未确认主控新鲜且全部停止，不执行')
    attempted=True
    session=post('gimbal/start',{})['session']
    end=time.monotonic()+4
    while time.monotonic()<end:
        post('gimbal/heartbeat',{'session':session})
        data=get();result['samples'].append(data)
        if not data['connected'] or not data['control']['active'] or not data['gimbal']['active']:raise RuntimeError('云台会话或P9失效，立即结束本次检查')
        if data['gimbal']['yaw_us']!=1500 or data['gimbal']['pitch_us']!=1500:raise RuntimeError('输出偏离本次固定中心检查，立即结束')
        time.sleep(.25)
    result['status']='UNLOADED_P9_COMMAND_PATH_PASS; DOES_NOT_PROVE_POWER_CAUSE_OR_LOADED_SERVO_RECOVERY'
except Exception as error:
    result['status']='FAILED_OR_INCOMPLETE';result['error']=str(error);failure=error
finally:
    if attempted:
        try:result['stop']=post('gimbal/stop',{})
        except Exception as error:result['stop_error']=str(error)
    try:result['final']=get()
    except Exception as error:result['final_error']=str(error)
    stamp=datetime.datetime.now().strftime('%H%M%S')
    path=out/(stamp+'-unloaded-command-check.json')
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(status=result['status'],samples=len(result['samples']),evidence=str(path)),ensure_ascii=False))
if failure:raise SystemExit(1)
