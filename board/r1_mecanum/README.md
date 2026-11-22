# 麦克纳姆轮软件交付 · 2026-10-26

已完成主控控制代码、手机网页与 Android 转发、电脑 P9 转发，以及对应构建和离线检查。当前为待装轮联调版本，未烧录、未安装 0.26、未执行车轮动作。

## 本次实现

- 前后、左右横移、四个对角平移、原地左右旋转；键盘支持平移与旋转合成。
- 手机摇杆左右改为横移，原地旋转使用独立按钮；方向键平移，Q/E 旋转，空格停止。默认速度档 20%。
- 能力协商确认麦轮固件后才开放横移；新版手机连接旧差速固件时保留原左右转向。
- CH32 内完成四轮混合与限幅。手机/电脑发送车体方向，不能直接绕过主控逐轮输出和保护。
- 延续原 600ms 指令失效、会话代次/递增序号、松手归零、换向缓停、失速/反转反馈/超速和电压保护。测距仍是手动拍摄模式下的提示。

## 文件入口

| 内容 | 项目根目录下路径 |
|---|---|
| 主控增量源码 | `知行回路软件/board/r1_mecanum/` |
| 保留所有现有传感代码的完整编译快照 | `知行回路软件/build/r1_mecanum/source-snapshot/` |
| 主控产物 | `知行回路软件/build/r1_mecanum/r1_mecanum.bin`、`.hex`、`.elf` |
| 手机与电脑界面源码 | `知行回路软件/debug_ui_mecanum/` |
| 0.26 手机安装包 | `output/onboard_dashboard/mecanum-20261026/zhixing-dashboard.apk` |
| 统一交付状态与哈希 | `output/onboard_dashboard/mecanum-20261026/delivery.json` |
| 主控和 Android 检查 | `output/onboard_dashboard/mecanum-20261026/checks/results.json` |
| 电脑协议检查 | `output/onboard_dashboard/mecanum-20261026/checks/pc-results.json` |

旧 `debug_ui/`、旧主控构建、当前安装应用均保留。本分支在同级独立目录构建，避免覆盖其他聊天正在处理的相机/算法或传感界面。`debug_ui_mecanum/` 内沿用的历史相机安装脚本不作为本版部署入口。

## 四轮约定

车体正方向是前进、向右横移、顺时针转动。每个轮子的正速度均指向车头方向滚动。厂家编号保持 M1 左前、M2 左后、M3 右前、M4 右后，按 X 形滚子布局推导：

| 轮子 | 混合目标 |
|---|---|
| M1 左前 | 前后 + 横移 + 旋转 |
| M2 左后 | 前后 − 横移 + 旋转 |
| M3 右前 | 前后 − 横移 − 旋转 |
| M4 右后 | 前后 + 横移 − 旋转 |

混合超过 ±250 时，四轮按同一个系数缩小，随后沿用厂家 ±1000 速度命令和现有四轮保护。命令是归一化控制量，不宣称 mm/s 或角速度；轮径、轮距和实际滑移尚未标定。没有持久改写驱动板原 65mm 参数，也不将其当作实际原轮径。

运动学参考：[WPILib 麦轮运动学](https://docs.wpilib.org/en/stable/docs/software/kinematics-and-odometry/mecanum-drive-kinematics.html)。本代码采用向右、顺时针为正的车体约定，并转换为本车 M1/M2/M3/M4 顺序；没有引入 WPILib 依赖或复制其实现。

## 协议与构建

固件身份：`R1_DRIVE_STARTUP_MANUAL_MECANUM_V1_20261026`。能力：`DRIVE_CAPS,5,250,600`。`DRIVE_CHASSIS` 必须确认 `MECANUM_X,FL_RL_FR_RR,250,600`。

新命令 `DRIVE_VECTOR,代次,序号,前后,横移,旋转` 三轴分别为整数 ±250；旧 `DRIVE_SET` 在麦轮固件上拒绝，防止旧的两侧命令误当成全向命令。`DRIVE_STOP`、`DRIVE_BRAKE` 保留，`DRIVE_VECTOR_STATUS` 可读回三轴和四轮目标。

用本机 Python 执行 `知行回路软件/tools/build_r1_mecanum.py` 编译固件；Android 使用 JDK17，执行 `知行回路软件/debug_ui_mecanum/build_android.py`，并设置 `ZX_DASHBOARD_BUILD_WORK`、`ZX_DASHBOARD_BUILD_OUT` 到本版独立目录。两个构建均不访问设备。

`prepare_mecanum.py`、`prepare_mecanum_controls.py`、`prepare_mecanum_pc.py` 是首次派生入口，会重新生成本版对应文件；手动修改本分支后不要未经比较再次派生。固件构建按 `baseline-sha256.json` 核对旧 IMU 源码快照，主控本轮差异仅 5 个文件。

## 验证边界与下一步

RISC-V 固件编译、Android Java/Dex 与签名、实际 C 源码的主机检查、Android broker JVM 检查、电脑转发测试、Chromium 中的离线假接口操作已完成。网页覆盖十个方向、键盘合成、摇杆横移、松手制动、旧固件降级及 390px 布局；全部使用假接口，无真实串口/USB/电机动作。桌面浏览器结果不能算手机旧 WebView 或地面通过。

轮子到货后先核四轮安装方向、联轴器固定和干涉，再以悬空低档核对各轮正负方向及停止，才进入小范围落地横移。方向不符、蹭线、异响、连续无转动反馈时立即停止。实际负载、横移偏差、重启后传感恢复、手机 P7+相机并发及耐久仍待现场验证。

驱动控制线断开时的独立硬件停车仍未解决。现有断指令/反馈保护不能冒记成已解决该问题。电脑入口保留烧录读回与主机验证凭据检查，当前没有伪造 `flash-verification.json` 来开放未部署版本。
