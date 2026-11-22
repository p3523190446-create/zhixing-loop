# 第一块OLED通信检测

2026-10-07：PB8=SCL、PB9=SDA、VCC=3V3、GND=已验证主控地。串口OLED_STATUS连续两次读到0x3C应答，0x3D未应答、总线错误0、空闲两线高；测距仍更新。

仅通信通过。控制器/分辨率未确认，未初始化显示；屏幕黑屏不能判为损坏。接另外两块前先完成第一块显示。

独立软件I2C探测不改变PB6/PB7测距线。脚本flash_r1_oled_probe.py先备份既有视觉固件，失败尝试恢复；回读、握手、在线探测证据在build/r1_oled_probe/flash-oled-verification.json。现有视觉协议保持。

下一步核OLED尺寸/控制芯片并做显示测试；若无正常显示，停在单屏排查。
