from pathlib import Path
import json
root=Path(__file__).resolve().parents[2]
p=root/'比赛备案/项目状态.json'
data=json.loads(p.read_text(encoding='utf-8'))
data['updated']='2026-10-09'
data['phone_readonly_panel']={
    'date':'2026-10-09','status':'HTTP_VERIFIED_PHONE_ACCEPTANCE_PENDING',
    'route':'CH32 -> PC serial read-only relay -> same-LAN personal phone browser',
    'firmware_changed':False,'motion_commands':'NONE',
    'http_test':'PASS_READONLY_HTTP_FRESHNESS_AND_STALE_MASKING',
    'evidence':'知行回路软件/remote_panel/verification.json',
    'record':'比赛备案/14-手机实时状态页-第一版.md',
    'phone_network':'PENDING','visual_layout':'NOT_INSPECTED',
    'next_step':'Personal phone same network; open runtime URL and verify changing distance and uptime',
    'stop_condition':'Page unreachable or stale: resolve networking/relay before expanding',
    'standalone_car_host':'NOT_IMPLEMENTED','remote_motion':'NOT_IMPLEMENTED'}
data['current_board_firmware']['readonly_recheck_20261009']={
    'result':'PASS_FRESH_BATTERY_FOUR_SPEEDS_THREE_OLEDS_NO_MOTION',
    'evidence':'知行回路软件/build/r1_motor_dashboard/dashboard-20261009-001452.json',
    'physical_screen_acceptance':'PENDING'}
p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
shared=Path('C:/Users/panyuanhao/dsh人生规划/导师共识.md')
text=shared.read_bytes().decode('utf-8')
entry='''### 2026-10-09 · Codex：手机只读状态页第一版
- 当前固件r1_motor_dashboard只读复核通过：电池8.1V、四轮静止、三屏刷新通信正常；本次未烧录、未发送运动指令。实物屏幕显示仍待用户验收。
- 新增临时电脑串口转发的局域网手机状态页，显示真实距离、电压、轮速、运行时间和故障，超时清空旧值。HTTP持续更新、POST拒绝和过期遮蔽验证通过；主力手机同网访问及页面视觉尚待验收。
- 操控端是用户日常使用的主力手机；车载小手机保持现有连接。车载独立辅助主机、视频和遥控运动未实现，既有控制线失联停车问题仍延期。下一步手机同网打开状态页，移动目标验收数据变化；打不开或停更先排查网络与转发。
- 证据：机器人比赛计划/比赛备案/14-手机实时状态页-第一版.md；知行回路软件/remote_panel/verification.json。

'''
marker='## 8. 更新日志'
assert marker in text
if 'Codex：手机只读状态页第一版' not in text:
    shared.write_bytes(text.replace(marker,entry.replace('\n','\r\n')+marker,1).encode('utf-8'))
print('Progress and shared section7 recorded; no hardware actions.')
