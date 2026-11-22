# 手机直连CH32：只读通信自检

当前0.7：新增独立WCH串口回环模式，尚未实测。0.6最新回读的权限实际在约1.15秒后授予，之后八轮测试失败；没有permission_timeout事件。用户选“授权超时”与这批记录不一致，按日志定位为后续USB设置/接收失败，不归咎用户、也不假定另一次未记录操作。下方0.6“待测”说明为当时准备状态。

2026-10-13当前0.6：修正0.5授权回调过滤错误、增加20秒授权超时退出及授权前事件记录，手机实际授权与12/12尚待本轮验证。0.4最新回读出现两组三个重叠测试，手机Activity栈实查同应用三个页面，旧暂停页面也会接收同一权限广播并启动独立测试。这是已证实的程序缺陷，尚不能认定全部历史失败都由它造成。0.3回读三段设置及读回均成功，PING写入5字节后无RX；电脑回接P9实时通信正常。0.2全部停在CDC设置返回-1；0.1部分PING/STATUS完整但其他回复缺字节。固件仍r1_gimbal_wide，无改动。

## 接法

1. 断开开发板电脑USB、关开关；驱动电池保持断开，两只SG90三线插头暂时整组拔下，避免手机OTG同时带动舵机负载。
2. 小手机拔电脑线，改接手机→单口OTG→数据线→开发板P9/WCH-Link，先不接相机；不把开发板其他USB口接另一电源来补电。
3. 开发板ON；手机打开“知行回路主控自检”，点开始通信自检，允许USB访问。仅匹配当前电脑实测1A86:8010，对唯一CDC控制接口及数据接口操作，不触及类别255调试接口。
4. 固定115200/8N1，三轮PING、STATUS、GIMBAL_STATUS、ULTRA_STATUS共12条查询，正常自动结束。只有全部正确回执及日志正常落盘才标通信通过；未匹配/超时/字段错误/写入异常即失败，退出页面/拔设备停止。

不会发送运动、设置或烧录命令。这是手机单独带主控的短测，不是相机＋主控同时连接、独立整车供电、遥控或长时稳定验收。供电不稳/反复重启立刻拔OTG。电脑网页此时因P9离开电脑显示离线属预期。

## 记录与回读

应用自身files/board-link/时间编号/events.jsonl逐次保存TX尝试、主机接受字节及RX块的原始Base64、手机单调时刻与墙钟、USB接口/CDC配置、查询回执及结束/失败；0.2为独立线程写日志、约每秒fsync、结束时同步落盘。结果与原始数据不会在重装-r时主动删除。result.json记录汇总，不读取其他应用资料。APK为本项目可run-as的调试版，正式分发前需要改为应用内导出。

用户短测后把小手机接回电脑，运行同级collect_boardlinkprobe.py回读；若突然断电缺少结束事件，记录判中断而非通过。当前只读短测程序，最终后台记录/录像/网络操控另行集成。

## 构建与接口依据

运行phone_vision/build_boardlinkprobe.py。沿用已准备的Android工具和本项目开发签名，没有新增第三方库。

- [Android USB Host官方API](https://developer.android.com/develop/connectivity/usb/host)：授权、接口声明及bulk/control传输。
- [usb-serial-for-android官方项目](https://github.com/mik3y/usb-serial-for-android)：CDC按接口类别识别的参考说明。本应用自行使用Android API，不内嵌该库，不以库支持清单冒充WCH-Link手机实测。
- 当前开发板电脑已枚举USB串口COM5/1A86:8010/MI_01，调试MI_00另存；只能据此选择尝试P9，实际CDC描述符由手机记录核验。

## 0.1失败与0.2修正

手机回读13段旧日志，接口0为255调试，接口1为CDC控制、接口2为CDC数据；最后一轮SET_LINE_CODING返回-1，是真的USB控制传输失败，不能由放宽判断宣称成功。其余多轮返回7，部分完整PONG/STATUS，另有ONG、STATUS后半段及GIMBAL缺字段，均未达到12/12。用户确认手机连主控期间OLED距离实时变化，主控在运行；不能直接认定传感器接线或电池故障。

0.1发送后才读USB，且每个RX小包同步刷盘；日志可见大量1字节包及每包约8ms间隔。这是可修正的接收空档，尚未独立证实唯一根因。0.2先启动独立持续接收再发送，按USB包长连续读，原始日志由1024条有界队列交独立线程写，回复行另外组包。队列满/写失败不伪装成功；保留字段数检查，绝不把缺字段判通过。CDC设置负返回立即失败，非负返回继续并尽可能读回7字节参数。每条查询超时3秒，出错提前结束，界面不再误导成15秒强制倒计时。

旧原始证据output/phone_board_link/readback-20261013-113306，拼包分析first-failure-analysis.json；0.2部署以build-result.json及repair-v02-status.json为准。实际修复通过必须等本轮用户操作及回读，不从旧PING成功推断全部稳定。

## 0.2失败与0.3初始化恢复

0.2实际手机日志在output/phone_board_link/readback-20261013-114110，所有新版段均CDC SET_LINE_CODING返回-1，尚无TX查询；所以不能说0.2接收路径已通过或仍在丢包。故障尚未定位到唯一软件/供电原因。

0.3记录USB原始描述符、标准GET_STATUS/GET_CONFIGURATION返回（仅用于诊断，标准请求失败不自动等于串口不可用）。第一次CDC设置失败时，释放已占用CDC接口，确认配置唯一后重新应用该USB配置、重新占用CDC接口，等300ms只再试一次；仍失败明确停止。没有WCH调试命令、芯片复位或刷固件；USB重新配置会重置USB接口传输状态，不等于证明供电正常。增加两秒按钮重试间隔，显示版本及具体失败阶段，不连续自动重试。

0.3部署证据repair-v03-status.json；本轮通过仍待12/12实际结果及回读。若重配仍失败，先对照开发板回接电脑的原链路，区分手机USB兼容/供电与板端问题，再选择下一修复；不靠绕过错误、放宽字段或反复点击宣称修好。

## 0.3电脑对照与0.4异步接收

0.3实物并未卡在初始化：三轮USB状态/115200设置/读回均接受，发送PING后3秒无任何RX。用户回接电脑P9后COM5枚举、实时HTTP连续状态可读，云台输出零。先前未识别板时旧telemetry.json不作为当前证据。不能直接判板损坏或把手机收不到回执称为设置仍失败。

0.4输入改为两个预先排队的UsbRequest，无超时requestWait；完成后先补排队、保存收到的字节并组包。停止/超时/离开页面时取消请求、等待接收线程及日志落盘，再释放接口。没有短超时requestWait。按官方CommonUsbSerialPort的异步/多缓冲思路实现，没有内嵌其库：其源码说明短超时bulkTransfer可丢数据、短超时requestWait在旧Android可能崩溃；这是实现依据，尚不是本机问题唯一根因证明。

证据v03-pc-comparison.json及repair-v04-status.json，0.4实际通过待回读。参考[CommonUsbSerialPort源码](https://github.com/mik3y/usb-serial-for-android/blob/master/usbSerialForAndroid/src/main/java/com/hoho/android/usbserial/driver/CommonUsbSerialPort.java)。

## 0.5单会话与权限广播隔离

旧程序的working只在单个Activity内生效；后台旧页面仍注册权限广播，授权一次会使多个页面各开一个USB连接。最新原始记录1791864871141/1153/1161及1791864890650/0651/0682时间重叠，第二组三段设置可接受、接收空块/无RX/发送失败并存；不是单纯串口参数一直不接受。

0.5采用singleTask复用页面，进程全局锁跨页面独占USB，锁持有至接口/接收线程清理完成；接收线程无法关闭时保留锁、要求重启应用。每次授权使用独立随机标记、校验当前设备路径，只允许对应前台页面启动；授权弹窗期间返回结果先保存，页面恢复才开始；过期广播和后台旧页面不能启动。停止/拔下/退出会取消接收；记录页面随机ID、进程ID、版本，便于复核并行问题。保留原始字节及字段校验，没有添加运动指令。

参考[Android任务与返回栈](https://developer.android.com/guide/components/activities/tasks-and-back-stack)。编译/签名/重复打开页面验证与真实手机OTG通信分开记录，不把单页面修正当12/12通过。

## 0.6授权等待修复及证据边界

0.5为了隔离过期授权给PendingIntent加了自定义URI，但权限广播IntentFilter没有对应scheme，Android会拒绝这类回调。这是Codex新增的程序错误，不是用户没找到按钮。0.6移除URI，保留随机token/设备路径/前台/全局锁核验；旧PendingIntent用CANCEL_CURRENT替换。实际权限每500ms只读确认，20秒仍未授权或设备已消失则明确停止，禁止一直等待和循环重试；只有manager.hasPermission真才可启动。开始及设备插拔更新设备列表，避免底部残留“未发现”旧文字。

授权请求/回调/过期回调拒绝/实际权限确认/设备插拔/超时保存在files/board-link-ui.jsonl，供回接电脑后collect_boardlinkprobe.py读取。启动时在真实Android运行IntentFilter.matchData检查旧URI不匹配、新无URI匹配；这不模拟或授予USB权限。旧手机数据不删除。

新读取readback-20261013-124439中五段0.5全部同一页面/进程，时间不重叠；部分标准USB及CDC设置成功，PING主机写入5字节但无RX，其他轮次仍USB设置负返回。说明多页面冲突已消除但完整通信未恢复；修授权不能冒称解决后续收发。系统日志曾记录授权页面启动/显示，但不能证明用户看到或点击；本次无弹窗原因仍须新授权日志核验。

依据[Android IntentFilter匹配规则](https://developer.android.com/reference/android/content/IntentFilter#matchData(java.lang.String,%20java.lang.String,%20android.net.Uri))和[USB Host授权说明](https://developer.android.com/develop/connectivity/usb/host)。没有主控固件修改、运动命令或系统USB授权绕过。

## 0.7分段回环定位（准备，未实测）

先用电脑基线验证跳帽回环，再改接手机对照。全程驱动电池和两只舵机电源断开；更换跳帽时开发板USB拔下、开关OFF。

J2最上面两排分别为RX1↔TX_0、TX1↔RX_0。两只原跳帽各横跨左右两针。先取下两只横帽，一只收好，另一只转90度纵跨右列的TX_0和RX_0。左列RX1/TX1保持空。不要移动下面RST0/3V3/GND或调试跳帽。标识看不清或帽不合适就停，不凭照片朝向猜电源针。

这使WCH UART发送直接回到自身接收，CH32 UART已与它隔开。电脑pc_wch_loopback.py必须显式--j2-loopback-ready，只向唯一1A86:8010端口发ZX_PC_A01/B02/C03各一行，逐字节比对、保存原始收发。串口被网页服务占用需先由本任务停止已核验服务，脚本不会自行杀进程或改USB配置。

电脑回环通过后，手机0.7点“WCH串口回环测试（须改J2跳帽）”，发ZX_LOOP_A01/B02/C03三行，严守原样内容（不去空格或CR）并保留所有原始字节。成功只称WCH回环3/3，不称主控12/12。旧“主控通信自检”只在恢复两只横向跳帽后使用。

若手机停在USB设置，说明尚未到回环字节阶段；若电脑通过、手机回环失败，可将当前问题范围收窄到手机/OTG/WCH USB串口链路，但不能单独认定手机、转接头或供电谁坏。两端回环通过但恢复后主控无回复，再查UART/复位和主控。测试结束必须断电恢复原横帽，回环期间不做云台或车辆控制。供电反复重启/掉电即断OTG。
