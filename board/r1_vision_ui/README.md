# 当前上板：视觉显示修复（2026-10-07）

- 当前主控固件 r1_vision_ui；第一OLED PB8/PB9，第二OLED PB10/PB11。两屏3V3供电，独立软件I2C，同为0x3C也不冲突。
- 第二屏完整支持模型0–79的80类中文名称：62显示屏、63笔记本电脑、66键盘。模型分数不是识别正确率。
- 新鲜视觉数据超过2秒未收到显示未连接；正常空检测显示无目标。原测距300ms故障阈值、灯和蜂鸣器、传感器恢复保持原实现。
- 手机使用 zhixing-vision-steady.apk：256输入、两线程、至少750ms一次识别。每帧预览绘制最近识别框；新空结果/错误立即清框，超过1500ms清框。不是运动跟踪，不把缓存框重新发布成新识别。

## 已验证

- MCU编译、旧版完整备份、下载及读回、UART握手，两屏ACK与刷新、测距采样通过。
- 实际第二屏渲染源码在电脑测试：80类均有字形，最长名称不超屏；这是模拟屏幕总线，不是人眼实物验收。
- 实际主控接收80类合成协议包，逐一返回对应中文编码；1.25秒保持、2.25秒过期清除通过。合成输入测试不是手机识别证据。
- 用户直接确认“目标框稳定，中文名字正常”，记为PASS_USER_REPORTED；未逐一摆出80类实物，未验收识别正确率。
- 三分钟真实手机链路结果另见 output/phone_vision/steady-180s-verification.json；历史整机watchdog根因仍未知，短测不证明根治。
- 当前视觉链路仍需电脑USB ADB转UART，不是独立车载通信，没有接入电机。

## 重建、证据与回退

- 构建 tools/build_r1_vision_ui.py；上板 tools/flash_r1_vision_ui.py。
- 主控证据 build/r1_vision_ui/flash-display-verification.json、label-render-host-verification.json、label-uart-verification.json、physical-ui-verification.json。
- 手机构建 phone_vision/build_steady.py，安装包 output/phone_vision/zhixing-vision-steady.apk。
- 回退主控 ch32-tools/r1-oled-dual/r1_oled_dual.elf；手机旧低负载和320版本均保留。
- 下一步正常使用观察；若再次卡死/重启、目标框异常消失或中文显示错误，停止本轮视觉测试并保留现象定位。
