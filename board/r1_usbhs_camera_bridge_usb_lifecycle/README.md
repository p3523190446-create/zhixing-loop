# Normal features with P7 native USBFS

Copied from verified r1_gimbal_wide. Original range/recovery, three OLED,
warning lamps/buzzer, USER mute/save, storage, HC-SR04 and gimbal safety remain.
PA11/PA12 now belong to P7 native CDC, 1A86:FE0C. P9 USART1 code is retained,
but two PC PING attempts after integration timed out; cause is not established.
Use the verified P7 route for phone communication and P9 for flashing/debug.
USBFS shares the existing read-only query parser with a scoped reply sink,
separate line buffer, 192-byte replies segmented into 64-byte USB packets.
USB bus reset discards pending messages. There is no physical UART2 bridge.
Native PING/NATIVE_ID and three fixed echoes remain compatible with v0.8.
USB accepts only exact read-only queries. It cannot arm or move motors/servos,
change settings, save data or inject vision. Unknown commands return an error.
The original motor motion gate remains disabled; servo PWM is zero on boot.

Do not connect P9 and P7 power simultaneously during this test. Motor battery
and both servo power supplies must remain disconnected for initial verification.
Compilation, flash/readback, PC query and phone query are separate gates.

## Verified 2026-10-13

- Flash and bytewise readback: build/r1_gimbal_usbfs/flash-verification.json.
- PC P7: 12/12 normal queries, all three OLED frame counters advance,
  settings reads, no servo PWM, unknown USB query rejected.
- Android 0.10 P7: 12/12 queries plus NORMAL_USBFS,1 identity. All 133 TX
  and 404 RX bytes match the saved commands/replies exactly. Uptime and ToF
  shot counters advance; ToF/ultrasonic valid; servo active/PWM zero.
- Phone evidence: output/phone_board_link/phone-normal-usbfs-proof.json.
- These were short read-only trials with motor battery/servo supplies off.
  Simultaneous camera+board USB, independent whole-car power, remote control,
  moving-car disconnect safety and endurance remain separate unverified work.
