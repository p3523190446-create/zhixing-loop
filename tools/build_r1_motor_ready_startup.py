"""Attach driver stream only after blocking sensor/flash initialization completes."""
import hashlib,json,shutil
import build_r1_motor_ready as previous
build=previous.build
build.STEM='r1_motor_ready_startup';build.WORK=build.TOOLS/'r1-motor-ready-startup'
build.OUT=build.PROJECT/'知行回路软件/build/r1_motor_ready_startup'
base_prepare=build.PREPARE
def prepare():
 base_prepare();u=build.WORK/'User';edit=previous.previous.edit
 edit(u/'main.c','vision_uart_init();motor_probe_init();','vision_uart_init();')
 edit(u/'main.c','    last_tick=tick_ms-1u;','    motor_probe_init();\n    last_tick=tick_ms-1u;')
 edit(u/'motor_probe.c','    USART_ITConfig(USART3,USART_IT_RXNE,ENABLE);USART_Cmd(USART3,ENABLE);',
      '    (void)USART3->STATR;(void)USART3->DATAR;\n    USART_ITConfig(USART3,USART_IT_RXNE,ENABLE);USART_Cmd(USART3,ENABLE);')
 edit(u/'remote_drive.c','R1_MOTOR_READY_20261020','R1_MOTOR_READY_STARTUP_20261020')
build.PREPARE=prepare
if __name__=='__main__':
 build.main();snapshot=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snapshot,dirs_exist_ok=True)
 p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
 d.update(date='2026-10-20',scope='Single-wheel PWM250/250ms; driver UART enabled after blocking startup to avoid retained stream overflowing RX ring; flush UART stale status; strict zero cumulative errors/drop guards retained',flash='NOT_RUN',physical_acceptance='NOT_RUN',driver_wire_disconnect_stop='UNRESOLVED',all_source_sha256={x.relative_to(snapshot).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snapshot.rglob('*') if x.suffix in ('.c','.h')})
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(d['binary_sha256'])
