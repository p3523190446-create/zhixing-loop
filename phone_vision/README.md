# 知行回路：安卓辅助视觉与USB结果接收

## 当前持续同步服务（2026-10-07）

当前主控r1_phone_auth；手机仍是zhixing-vision-steady.apk。电脑后台monitor_bridge.py默认持续运行，每两秒检查手机/应用、每秒心跳，自动重建手机与串口链路；仅新推理更新目标。启动/停止：工作区根目录启动视觉同步.cmd、停止视觉同步.cmd，重启电脑后需重新启动。状态：output/phone_vision/monitor-status.json。屏幕区分转发离线、手机离线、待授权、程序未运行、无新数据、无目标/有目标。详情见board/r1_phone_auth/README.md。下面有限时长的bridge_ch32.py为历史/诊断入口，不代表当前后台会到期停止。

## 当前版本（2026-10-07，修复目标框与中文名称）

`output/phone_vision/zhixing-vision-steady.apk` 已安装；当前主控 `r1_oled_triple`，第三屏PB12/PB13显示运行秒数与视觉状态。手机每个预览都绘制最近的框，仅新推理发布新数据；空结果/错误清框，缓存1500ms过期。完整80类中文名称在主控显示，视觉断联阈值改为2秒，测距300ms故障阈值不变。用户确认“目标框稳定，中文名字正常”。重建运行 `build_steady.py`；三分钟真实转发证据见 `steady-180s-verification.json`。下面320版与首个低负载版是历史记录，不代表当前参数。

## 已完成与尚未完成

2026-10-07：自建安卓应用已在SOYES K99（系统报告Android 9 / MT6739）安装，用户确认相机画面清晰。电脑通过USB ADB收到真实模型结果。本轮20秒记录76帧，接收约3.77帧/秒，单次检测耗时中位数245.32ms，格式异常0条。

最初为手机→电脑的数据链路短测。随后已接通电脑→WCH串口→CH32，并在20秒短测中收到57帧真实手机数据的逐帧匹配回执（56帧有目标、1帧无目标）。没有接入电机，没有验收识别准确率、端到端停车时延、独立车载运行或长期稳定。此前原应用有整机重启，原因字段watchdog，根因未确认。分类置信度是模型分数，不能把它当实际正确率。

用户已明确跳过中央/左侧/右侧的实物位置验证，该项仍未通过。CH32当前只接收视觉数据，不让视觉控制电机。下一步可通过已有OLED展示距离与识别结果，先核对屏幕接口。重启、卡死或明显过热时停止本地推理测试。

## 已通过的CH32串口短测

板上J2最上面两排跳帽由用户确认已连接，电脑当前识别为COM5。新固件先备份原测距程序，再下载并逐段读回核验；握手、正常包、错误校验、重复帧、非法类别、超长行恢复、无目标包、一秒超时清除均通过。测试时测距轮次35→49、有效读数持续更新。

桥接命令：`bridge_ch32.py --port COM5 --duration 20`。电脑保留已授权手机USB和开发板WCH-Link USB连接，手机打开「知行回路视觉」。若回到手机桌面，相机暂停，就不会有新帧；本轮已遇到此状态，重新打开应用后实测通过，不把无新帧误记为成功。

短测结束时清除目标，脚本停止后不持续转发。结果在 `output/phone_vision/bridge-verification.json`，逐帧真实输入与回执在该记录所指jsonl。当前数据选择每帧分数最高的一个目标，只验证传输；没有独立核对类别准确率。串口时延字段只计电脑发包到回执，不含相机取图与识别耗时。

## 手机测试应用

- 应用名：知行回路视觉；包名：`cn.zhixing.vision`；独立安装，不覆盖原作者演示应用。
- 固定COCO / YOLOv8n / 320 / CPU，仅保留一个模型，安装包约12MB。
- 只请求相机权限，无网络上传功能。
- 原始检测框仍在手机显示；另输出置信度≥0.35的有效对象，每帧最多8个。
- 手机界面有帧序号与单次识别耗时；没有目标也输出空列表，避免把上次目标当当前目标。
- 新增JNI读取结果入口；当前电脑接收通过ADB日志标签`ZXR_VISION`，尚未实现手机OTG串口。

APK：工作区 `output/phone_vision/zhixing-vision-debug.apk`。签名是本机开发签名，校验结果在同目录`build-verification.json`。

## 数据格式

一帧一个JSON对象：`v`、`seq`、`phone_ms`、`infer_ms`、`width`、`height`、`task`、`objects`、`truncated`。

每个目标：`cls`（COCO编号）、`score`（模型分数）、`cx/cy`（中心位置）、`w/h`（框宽高）。位置及尺寸归一化为0～1，坐标对应手机显示的检测图像。**框的位置和大小不是厘米距离。** `phone_ms`是手机单调时钟，与电脑墙上时间不可直接相减。`infer_ms`只计检测函数耗时，不是手机到电机的总时延。

PC接收器添加类别名称、中文名称（常用类）、左/中/右位置和接收时间；只读真实日志，不生成模拟目标。接收停止后`latest_detection.json`标记`monitor_stopped`，不应当作持续更新的控制输入。

## 本机运行

使用本机Python运行`receive.py --duration 30`。保持唯一已授权的手机连接并打开新版应用。默认ADB为工作区`tmp/android-tools/platform-tools/adb.exe`。

输出在工作区`output/phone_vision/`：

- `phone-detections-时间.jsonl`：每次接收的真实帧。
- `latest_detection.json`：最后一帧及接收状态。
- `receive-verification.json`：帧数、接收速率与证据文件路径。

不能把这条USB调试链路当作脱离电脑的手机→CH32连接；当前仍需电脑和USB线。

## 重建与来源

需要JDK17（本机已存在），设置`JAVA_HOME`；先运行`bootstrap.py`，再运行`build.py`。工具只解压到用户缓存`~/.cache/zhixing-android-tools`，构建在`~/.cache/zhixing-android-build`，没有安装全局Android Studio或Gradle。

模型从校验过的原作者APK读取，不下载任意第三方模型。重建前准备原作者固定版本到工作区`tmp/android-tools/ncnn-android-yolov8-20260527.f1ac75e.apk`：

- 来源：https://github.com/nihui/ncnn-android-yolov8/releases/tag/20260527.f1ac75e
- SHA256：`dfaa20c931918a6281bedcef9292d68895537d1046774fa0c6f4fc32d3bb3be8`

保留的原作者源码在`upstream/`，出处与版本在`upstream-provenance.json`，修改在构建缓存副本上应用；新增导出器在`native/`，安卓界面在`android/`，原代码版权及许可头保留。构建输入固定NDK r29、Android平台33、build-tools35、CMake3.31.5、ncnn20260526、opencv-mobile4.13.0；来源及校验值在`bootstrap.py`及`build-inputs.json`。

完整重建：下载并校验依赖→编译ARM64原生库→编译Java/Dex→封装最小模型→签名并验证APK。编译通过和上机证据分别记录，不互相替代。


## 2026-10-07：低负载试验版

- 原320版真实转发351帧后手机数据流中断，用户报告卡画面并自动重启，重启原因属性为watchdog；具体触发原因未知，不能据此断言过热、内存泄漏或算力不足。电池温度报告25°C并非CPU温度。
- 用户确认第二OLED已显示最高模型分数目标及分数；识别正确率未独立验收。
- 新独立构建：build_lowload.py，缓存zhixing-android-build-lowload，APK output/phone_vision/zhixing-vision-lowload.apk。原320 APK保留作回退。
- 固定256输入、ncnn两线程、OpenMP blocktime=0、OpenCV一线程、最多每秒8次画面转换、至少750ms才开始下一次新推理；相机图像先复制，再归还原生缓冲区，随后推理。加载/输入/提取失败与COCO输出形状不匹配时返回错误，不越界索引。
- 线程等待优化依据：[ncnn官方FAQ](https://github.com/Tencent/ncnn/wiki/faq)。此处是降低持续负载的候选修改，不是已定位watchdog根因。
- 新版编译/签名/安装通过，180秒真实转发218帧（168有目标、50无目标），结束后手机ADB和应用仍响应，数据跨度177.4秒、平均推理218.2ms；只能称短测通过，非根治证明，画面是否顺滑还需本人观察。
- 最大有效帧间隔1166ms，超过主控当前视觉超时1000ms，故运行期间存在偶发显示未连接的风险；不延长主测距故障的300ms阈值。当前有限转发结束后未连接为预期。尚未实现无需电脑的持续手机直连。
- 证据output/phone_vision/lowload-180s-verification.json及对应真实JSONL；原中断记录bridge-n320-freeze-20261007.json。
- 下一步观察新版画面是否随移动更新；若再卡死/重启则停止本轮视觉运行，保留记录继续定位，不强行把短测说成稳定部署。
