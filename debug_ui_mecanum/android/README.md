# 小安卓车载调试台

统一入口：**知行回路调试台**，包名 `cn.zhixing.dashboard`。小安卓运行HTTP服务并存放网页资源；主力iPhone是浏览器客户端，CH32仍负责主控决策。车载演示不需要电脑。

## 日常打开

1. iPhone开启个人热点，小安卓连接该热点。
2. 小安卓打开“知行回路调试台”，等待顶部显示完整网址，可点“复制网址”。
3. iPhone从桌面打开Safari，在地址栏输入该网址，保留`http://`和随机路径。
4. 2026-10-13已由用户确认：拔掉小安卓至电脑USB后，页面刷新和“运行状态／记录回放”切换正常。

此次实际地址为 `http://172.20.10.8:8780/6f8e7ddd60c24c1aab6502f9f8a80410/mobile`。IP和端口以应用显示为准，不把此次地址永久写死。服务前台通知与CPU唤醒锁已实现；锁屏长时、电量和整车供电仍待验收。

## 功能与验收

| 功能 | 当前证据 |
|---|---|
| 电脑版/手机版UI及模块封装 | 同源网页；模拟浏览器71项及旧后台只读20项通过 |
| Android内置HTTP、网页资产 | 已编译安装；真实Android接口检查24项及本机显示通过 |
| iPhone热点访问、拔电脑独立浏览 | 用户实测通过；可刷新及切页 |
| P7主控只读通信 | 旧carconsole 0.2实测80.324秒/800回复，另段后台14.046秒/147回复及完整保存；新dashboard包待实测 |
| 云台遥控 | 当前P7返回ERR,USB_READ_ONLY；API和网页禁用，broker仅模拟自检 |
| 外接摄像头、录像与时间回放 | 代码已实现，新包待实测；“记录回放”可切页不等于已有真实录像 |
| 摄像头和主控同时USB | 现有单口OTG不足，集线器及供电方案待验 |
| 电机运动 | 禁用；未发运动命令 |

## 文件与边界

`MainActivity`承载本机网页及动态地址；`GatewayService`运行前台网页服务；`LocalHttpServer`提供固定HTTP接口。`DiagnosticActivity/TelemetryService`拥有USB及原始收发日志，`TelemetryCodec`映射真实遥测；无连接或数据过期时返回空值。`ExternalCamera/HeadlessSurface`负责外接USB相机；`VideoRecorder`负责手机本地JPEG、帧索引和状态记录。前端所有功能位于`../assets/features/`，两端共享。

遥测原始记录和网页事件分别保存，未开启原始记录时页面明确提示。视频按Android单调接收时刻对齐，不是硬件同步；不宣称捕获CH32没有发送的内部事件，也不宣称全系统错误均有无损留存。

## 保留旧记录

全部28份旧原始文件、9段会话及UI日志已按原字节备份，并封装为 `output/onboard_dashboard/legacy-carconsole.zip`，逐文件长度、SHA256及ZIP回读核对通过。没有卸载或清除旧应用数据。这些是通信日志，不含视频，不出现在视频回放列表里。

`../import_legacy_records.py`默认只验证和打包；加`--import-device`时，经ADB写入dashboard独立的`files/imported-carconsole/`并逐文件回读核对。当前手机已拔电脑，**设备内导入尚未执行**；可导入归档已准备完成。不要运行`tmp/prepare_dashboard_android.py`，它会覆盖后续源码修改。

## 下一步实物验收

小安卓保留iPhone热点；电机和舵机继续断电，P9留空。以后接OTG→CH32 P7，打开调试台“连接主控”，按原生记录页面开始并允许USB；核iPhone实时状态更新、后台回复和停止保存后，再回读新包记录。出现USB错误、掉电或重启就停止并保留日志，不进入动作测试。此步骤尚未由用户完成。

## 构建与已安装版本

构建脚本`../build_android.py`，使用既有JDK17/Android工具缓存，生成签名APK。安装和自检证据位于`output/onboard_dashboard/`。`network-acceptance.json`登记此次通过的已安装APK SHA256；之后源码修订的新构建不自动继承其真机验收。手机当前已脱离电脑，不为写文档而要求重新接线。
