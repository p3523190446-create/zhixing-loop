# P9 USB observer (deployed 2026-10-20)

Based on the deployed DMA-recovery firmware. Adds only the P9 UART read-only
USB_STATUS query. USB allowlist, motion gates and endpoint behavior unchanged.

Fields: uptime_ms,address,configuration,enumerated,sleep_bits,queue_generation,
rx_bytes,tx_packets,rejected,overflows,pending_rx,in_busy,interrupt_flags.
queue_generation includes boot and interface resets, not just physical bus resets.
This cannot observe Android permission, popup or app ownership.
Full backup, flash and bytewise readback passed. SHA256:
15919e861e9ebfcea43e3d74b6f2dc4b70b158fc87e73715b19e91a3bfe579d6.
Live evidence is in output/onboard_dashboard/usb-recovery-20261020.
Firmware deployment is not phone/hub acceptance; each observation states its
scope separately, including whether PC P9 and active video were present.
