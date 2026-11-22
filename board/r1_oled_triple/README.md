# 当前上板：三块OLED（2026-10-07）

| 屏幕 | SCL/SDA | 显示 |
| --- | --- | --- |
| 第一块 | PB8/PB9 | 距离与安全、警戒、故障 |
| 第二块 | PB10/PB11 | 最高分目标的中文名字、模型分数 |
| 第三块 | PB12/PB13 | 系统状态、运行秒数、视觉连接/目标状态 |

三块屏幕分别使用独立软件I2C，共同3V3和GND；均实测0x3C响应。控制器型号仍未独立确认，采用SSD1306 128×64兼容驱动。

## 程序与验收

- 主控当前r1_oled_triple；手机仍是zhixing-vision-steady.apk。
- 每轮只写一块屏幕的32字节，三屏轮换，测距和UART持续服务；各屏独立错误/重试。
- 原测距恢复、声光定时、第一第二屏业务实现、80类中文表与2秒视觉过期逻辑保留。第三屏新增运行时间和实时视觉状态。
- 编译、烧录、完整旧版备份、读回、UART通过；三屏ACK和刷新通过，ready=1/errors=0，距离采样持续、传感器初始化正常。
- 用户确认第三屏“显示正常，数字会增加”，实物显示验收通过。新增屏幕不表示已验证所有拔线/电源故障。
- 手机仍经电脑USB ADB转WCH串口，有限转发结束后两块视觉相关屏显示未连接是预期。

## 文件与下一步

- 构建tools/build_r1_oled_triple.py，下载tools/flash_r1_oled_triple.py。
- 证据build/r1_oled_triple/flash-display-verification.json及physical-screen-verification.json；手机短测output/phone_vision/triple-screen-bridge-verification.json。
- 回退固件ch32-tools/r1-vision-ui/r1_vision_ui.elf保留。
- 下一步检查第三屏标题、数字递增、视觉状态；黑屏、乱码、数字停住或原测距灯异常时停止扩展并反馈具体症状。
