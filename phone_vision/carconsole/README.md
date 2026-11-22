# Car phone console 0.2

The CH32 remains the main controller. This independent Android package does
not replace the already verified boardlinkprobe and preserves its old logs.
It uses the verified two UsbRequest receive buffers and native P7 CDC route.

- Real distance, uptime, mute/warning, gimbal, screen transport and motor
  feedback freshness from existing exact read-only firmware queries.
- Foreground service owns USB; closing the Activity does not stop recording.
- Partial wake lock is held only while connected. Notification and UI can stop.
- No automatic reconnect, motion, arm, parameter write or firmware update.
- One complete state cycle per second. Old data is invalid after 2.5 seconds
  or immediately after connection stops; it is not shown as live distance.
- Separate sessions: session.json, events.jsonl, result.json. Full raw TX
  attempts/accepted portions/RX Base64, monotonic/wall times, parsed replies,
  errors, disconnect reason, device descriptors/control results and phone
  power/temperature are retained. Writer queue is bounded and fsync runs
  about every second. Unexpected termination may lose the unsynced tail;
  missing result/finish is marked interrupted, not complete.
- Storage below 64MB, writer failure, malformed/late replies or stopped/reset
  MCU uptime cause recording to stop explicitly. No old sessions are deleted.
- Camera video/network/remote controls are not included in this first slice.

Physical gates: phone P7 foreground recording, background continuity, clean
stop and complete raw log readback remain separate from compilation/install.
During initial tests keep motor battery and both servo supplies disconnected,
P9 unplugged, one USB power source only. Power/reset instability ends the test.

## 0.1 evidence and 0.2 change

The first long session logged 520 replies over about 51 seconds, including
50 replies while its Activity was in the background. A later 100-reply session
closed cleanly on USER_STOP. Two receiving sessions stopped on an empty USB
completion; several reconnect attempts failed before data transfer. Therefore
the 0.1 endurance gate is not passed. Exact physical/host cause is unproven.

0.2 uses API26 queue(ByteBuffer) with direct buffers. Every empty completion
is recorded and requeued; it does not manufacture a successful query or reset
its deadline. Matching replies still must arrive within 3 seconds. A run of
32 empty completions, queue/control errors or actual detach still stops.
Old sessions are retained. No MCU firmware or motion changes are made.

## 0.2 physical verification, 2026-10-13

- Native P7 single-phone-host trial: 80.324 seconds, 800 matching replies,
  no receiver/session error, USER_STOP complete close.
- Separate 0.2 trial: 147 matching replies during 14.046 seconds in background;
  Activity returned and recording continued, then stopped cleanly.
- Exact TX attempt/accepted equality and complete raw RX identity+reply stream
  verified against retained events and manifests. Evidence:
  output/car_phone/v02-acceptance.json.
- Only short read-only recording with motor battery and servo power off passed.
  Hours endurance, load power, camera/video simultaneous, network and movement
  remain separate gates. These results do not prove the exact cause of 0.1 errors.
