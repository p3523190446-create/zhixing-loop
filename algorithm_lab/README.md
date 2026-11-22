# 知行回路算法调试

## 2026-10-26 原车相机电脑实验与手动对焦

用户确认将相机接电脑做算法实验后，本次实际识别的是原车145F:02EC，非借用04B4:00C3。已新增明确选择的`--original-camera`入口：原生640×480 MJPEG目标30fps，预览直接转发相机JPEG，不重复编码；固定USB身份，不回退内置相机。借用相机仍用`--borrowed-camera`，其UYVY配置保留。管理器拒绝在已有另一来源的服务上假报切换成功；仅重启本算法页，未重启8795服务。

本次原车真实预览与YOLOX CUDA已运行，状态短窗约30fps预览、约22—25fps识别；不是耐久或曝光到屏幕延迟验收。原车暂接电脑实验不改变“原车用于手机装车，借用相机用于电脑”的已选长期分工。当前P9不在线，不伪造真实巡线/姿态测试。

用户随后要求先手动旋转镜头对焦。现页新增当前清晰度、本次最高值、重置和放大对焦模式；在原始预览中心50%区域计算灰度拉普拉斯方差，固定320×240采样、3次中值平滑。每约150ms最多一次，重复源序号不采样，识别画面不算分（避免检测框增加边缘），无新鲜图像时清空当前值。分数只供同一场景、光照和距离下比较，无通用及格分数；更换物体后重置。实际最佳焦点尚需用户手动确定。

验证：既有算法6项、跟踪4项软件测试通过；清晰度受控纹理/模糊/纯色的排序通过；浏览器真实相机分数更新、重置、放大控件已操作核对。调焦后六种模式已完成指定真实场景实验；人物、人脸、红蓝和7号路标已观察连续锁定，绿色存在反光误锁，不能算目标选择准确通过；用户随后接受该光滑屏幕/自带灯场景限制，暂不优先处理。详细结果见[2026-10-26实验报告](../../output/onboard_dashboard/algorithm-experiments-20261026/实验结果-2026-10-26.md)。资料位于`output/onboard_dashboard/algorithm-experiments-20261026/`，含改前备份、相机模式、首帧、状态和manual-focus-panel.png。

```powershell
python manage.py start --original-camera --record-seconds 180
```

原有服务若选择了另一相机，先`python manage.py stop`再明确选择来源；不会自动重置USB设备或主控。

## 手机独立优先

用户已选手机本地运行，电脑GPU只作后备。[本机实测与迁移缺口](手机独立部署与实测-2026-10-25.md)。现8796为开发入口，不能当成已交付手机车载版。

## GPU与跟踪最新

第二轮已启用CUDA与约30fps预览/22fps识别流，增加连续目标跟踪、按需人脸分支与事件照片；[实际范围和验证](优化与跟踪-2026-10-25.md)。以下首轮说明保留作历史，15fps/CPU等旧状态由第二轮覆盖。

2026-10-25 首轮。入口 `http://127.0.0.1:8796/`，只显示算法结果，不发电机或云台命令。沿用原 8795 服务单独管理 P9，不抢串口、不改固件。新增模块放在现有软件目录内，便于后续接回共用调试台；并非五套开源整车工程均已移植完成。

**本轮最新状态：已按用户选择改用借用的USB031（04B4:00C3）直连电脑，真实图像和模型输出已通。** 驱动仅报告1920×1536 UYVY、标称30fps模式；没有据此宣称实际输入30fps或相机准确型号。用户随后要求按实际降低分辨率并指出网页帧率低，现由FFmpeg输出960×768、目标15fps，预览直接从采集线程走独立MJPEG，模型另读最新帧。2026-10-25本机HTTP连续接收46帧、2.985秒，15.075fps；同时检测约2.7fps、单次模型266ms。这是一次短测，不是耐久或曝光到执行延迟。浏览器实际图像960×768，显示预览15fps/识别2.7–2.8fps。

“流畅预览”是当前真实连续画面；“识别画面”是模型处理过的对应帧。两者分开，避免把旧检测框冒充当前帧。保存的`raw_frame`是未画框的960×768 JPEG，已不承诺每帧保存传感器完整分辨率。先前1920×1536采样留在之前的run目录，未删除。此摄像头是借用资产，本轮PC实验通过不代表已长期车载部署。

## 本轮实际接入范围

| 方向 | 软件产物 | 验证与缺口 |
|---|---|---|
| Pololu 巡线思路 | 沿用实测黑白参考，八路加权位置、PD纠偏建议；全白、全黑、宽黑块、多段及过期不给运动建议 | 已接真实 P9 八路数据；X1/X8到车体转向对应和动态参数未验，没有巡线执行 |
| Waveshare 观察思路 | 红绿蓝色块中心偏移、相邻新画面变化比例 | 生成图检查颜色与运动变化通过；未执行云台追踪；画面变化可能来自光照或镜头移动 |
| Duckietown 路标思路 | OpenCV AprilTag36h11识别、编号候选和连续帧计数；附0/1/2号PNG | 生成7号路标识别通过；看见编号不代表到站，停车线和任务执行未接入 |
| 物体检测 | 官方 OpenCV Zoo YOLOX-s，80类，45%置信阈值，CPU后端 | 课程bus样例检测5个目标；旧相机录像3帧推理完成且目标均0。后来USB031真实连续采集、模型回包及浏览器图像通过；场景类别准确率、动态追踪和车载链路仍待验 |
| Linorobot 里程计思路 | `odometry.py`四轮合左右速度、源时钟积分和相对轨迹算法 | 人造直行/时钟重复/中断/复位检查通过；实测速度比例、方向和等效轮距缺失，实时轨迹未启用；没有ROS2/Nav2建图 |
| Donkeycar 采集思路 | 每秒记录原图（有新鲜画面时）、人工/主控状态和各数据年龄，单轮限时60秒、原图上限120MiB | 当前允许无图时记录车况；未验证相机固定和严格同步，所有记录 `training_ready=false`，没有训练驾驶模型 |

源帧超过1.5秒清空视觉结果；巡线年龄超过500毫秒不给纠偏。两者独立计时，不以新的HTTP请求刷新旧传感器或旧画面。界面展示的模型计算时间不等于相机曝光到机构执行的时延。

## 本轮初期链路检查（保留负结果，后来已改用USB031）

用户报告：集线器的数据上行线接电脑，摄像头和P7在集线器侧，由电脑供电。但本轮Windows设备列表仅有内置摄像头 `04F2:B828`，没有外接 `145F:02EC`、外置Hub或P7 `1A86:FE0C`；手机仍ADB在线、USB角色为device，host_connected=false，没有wlan0。

P9已做有界相机检查：`CAMERA_CAPS,1,160,120`，`CAMERA_START`返回`CAMERA_ERR,1`（按当前源码为USBHS未检测到接入）。原P9服务已按原地址恢复，无刷写/复位/MPU兼容开启/非零运动命令。P7是固件的USBFS设备通信口，不能仅由“P7→Hub→相机”的描述推断CH32正作为相机主机。旧实测正常路线是手机作为主机、P7和相机并列接Hub。

后来用户选择改用借用摄像头，Windows真实枚举出USB031，按该设备唯一USB身份取流；没有以电脑内置摄像头代替。本轮未解释旧摄像头/Hub不枚举的根因，不把新设备成功当旧链路已修复。

MPU当前无有效读数：非标准身份0x72在重启后被默认身份检查拒绝。既有水平参考仍在，没有静默绕过身份检查。

## 运行与停止

使用Codex内置Python：`C:\Users\panyuanhao\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`。依赖单独装在项目 `tmp/algorithm_deps`，不修改共享Python包；`requirements.txt`列运行本模块真正需要的包。当前准备环境另装有pyserial与onnxruntime，YOLOX实际用OpenCV CPU，没有调用GPU/云端付费服务。

在本目录执行：

```powershell
# 以下python请替换为上面的完整路径
python prepare.py                 # 固定官方commit，按Git LFS的SHA256校验模型
python test_algorithms.py         # 软件边界与人造图测试，不控制硬件
python verify_offline.py          # 旧录像/课程样例，明确不是当前实时图像
python manage.py start --borrowed-camera # 隐藏窗口启动USB031采集和只读算法页；首60秒记录关联样本
python manage.py status
python manage.py camera-start    # 仅启动电脑实际枚举的145F:02EC外接相机
python manage.py camera-stop
python manage.py stop            # 停止本算法服务及其USB031采集子进程；原P9服务不动
python measure_preview.py        # 只测真实MJPEG接收帧率，不发动作
```

输出：`机器人比赛计划/output/onboard_dashboard/algorithms-20261025/`。模型与源码固定在`vendor/opencv_zoo_yolox/provenance.json`，权重35,858,002字节，SHA256 `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063`。OpenCV在Windows不能直接打开中文ONNX路径，已将核验后的相同文件缓存到用户`.cache/zhixing-algorithm-models`，上游源码未改。

停止条件：相机不枚举则停在通信检查，旧画面不作实时结果；云台链路、物理断线停车、动态方向和标定没有通过，则本页持续只观察、不执行。整套开源功能要按原路线继续分阶段推进。

## 来源与复用

- [Pololu PID说明](https://www.pololu.com/docs/0J21/7.c)：借鉴位置误差与PD/PID思路，当前参数和本车实现独立编写，没有复制其底层驱动。
- [Waveshare视觉行为源码](https://github.com/waveshareteam/ugv_rpi/blob/main/cv_ctrl.py)：借鉴色块观察/画面变化行为；没有复制其树莓派运行环境或控制代码。
- [OpenCV路标检测文档](https://docs.opencv.org/4.13.0/d5/dae/tutorial_aruco_detection.html)：调用库的AprilTag36h11字典。
- [OpenCV Zoo YOLOX](https://github.com/opencv/opencv_zoo/tree/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/object_detection_yolox)：实际复用原版`yolox.py`和ONNX，Apache-2.0许可证随文件保留，来源/指纹在provenance.json；本地adapter独立完成缩放、边界裁剪、结果老化与界面。
- Linorobot/Donkeycar本轮是运动学与采样组织思路的适配，不宣称已安装、移植或运行整套框架。原五方向路线仍见比赛备案的持续完善路线图。
