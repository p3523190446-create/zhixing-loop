# CH32 USBFS独立诊断（临时固件）

目的：在同一手机、OTG和板上，用主控原生USBFS（P7，PA11/PA12）对照已失败的P9 WCH-Link复合USB通道；不据此宣称WCH硬件损坏。原上板版本r1_gimbal_wide保留，正常测距/三OLED/灯/存储/云台功能本诊断不初始化，距离屏会停止刷新；验证完成后恢复或把原生USB接入正式固件。

## 实现

- 使用本机WCH EVT USBFS/DEVICE/SimulateCDC的USB设备和描述符，保留WCH芯片专用版权限制。USB标识沿用示例1A86:FE0C，不声称拥有厂商VID/PID或已批准量产。
- 去掉实体USART2/TIM2/DMA串口桥；用只读软件队列代替UART2回调，避免PA2/PA3和原OLED2冲突。USB用PA11/PA12；主控固件编译工具与官方启动/时钟一致。
- 只接受PING→PONG、NATIVE_ID→NATIVE_USBFS,1、三个固定ZX_NATIVE回声；其余输入ERR,READ_ONLY。超长/控制字符/CR拒绝，USB复位清队列防旧回复重放。不能接收运动或设置命令。
- GPIO PD0–3置高，使既有低电平灯/蜂鸣器关闭，PA8/PB0置低，无任何PWM/电机/传感器初始化。电机电池与双舵机电源必须物理断开，GPIO状态不等于供电隔离。
- 0.8手机增加“USBFS直连自检（P7＋专用测试固件）”；只有目标FE0C可跑此模式，验证5条完整精确回复，成功只称独立诊断5/5。不把回声当距离/运动/长期稳定验收。

## 构建与上板门槛

tools/build_r1_native_usb_probe.py只编译，不烧；flash_r1_native_usb_probe.py未带--execute不访问硬件。上板前必须用户确认电机电池/舵机电源断开、J2恢复原两横帽、P9电脑且ON。

执行烧录会先读全256KiB、核对当前r1_gimbal_wide已验证二进制、写新程序、逐字节回读，失败恢复并核验全备份；不修改WCH-Link自身固件。PA11/PA12属于主控USBFS，本机官方评估板参考标P7；不能仅把手机改插P7而不烧专用固件。

先电脑P7测试CDC设置及五条回复，再断电拔所有电脑USB，手机单独OTG→P7，允许USB授权并测5/5。P9/P6均不同时供电；若USB连接/电源不稳或手机重启立即断开。当前状态以build_result.json/flash-verification.json/实测记录为准，编译成功不等于USB已枚举或手机通信通过。
