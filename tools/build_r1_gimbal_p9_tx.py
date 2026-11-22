"""Keep TIM5 gimbal and motor guards; make P9 UART reply draining interrupt-driven."""
import hashlib,json,shutil
import build_r1_gimbal_tim5 as previous
build=previous.build
build.STEM='r1_gimbal_p9_tx';build.WORK=build.TOOLS/'r1-gimbal-p9-tx'
build.OUT=build.PROJECT/'知行回路软件/build/r1_gimbal_p9_tx'
base_prepare=build.PREPARE
def replace(path,old,new):
    text=path.read_text(encoding='utf8');assert text.count(old)==1,(path,old)
    path.write_text(text.replace(old,new),encoding='utf8')
def prepare():
    base_prepare();u=build.WORK/'User';p=u/'vision_uart.c'
    replace(p,'static uint8_t tx[256];\nstatic uint32_t tx_head, tx_tail, seen_errors;',
        'static volatile uint8_t tx[256];\nstatic volatile uint32_t tx_head, tx_tail;\nstatic uint32_t seen_errors;')
    anchor='''            rx_head=next;
        }
    }
}

void vision_uart_init'''
    replace(p,anchor,'''            rx_head=next;
        }
    }
    /* TIM2 remains priority0. RX and TX share this priority1 UART IRQ. */
    if(USART_GetITStatus(USART1,USART_IT_TXE)!=RESET){
        if(tx_tail!=tx_head){
            USART_SendData(USART1,tx[tx_tail]);tx_tail=(tx_tail+1u)&255u;
        }else USART_ITConfig(USART1,USART_IT_TXE,DISABLE);
    }
}

void vision_uart_init''')
    replace(p,'unsigned i, n=(unsigned)strlen(message);\n    if(n>255u-((tx_head-tx_tail)&255u))return;\n    for(i=0;i<n;i++){tx[tx_head]=(uint8_t)message[i];tx_head=(tx_head+1u)&255u;}',
        '''unsigned i, head=tx_head, n=(unsigned)strlen(message);
    if(n>255u-((head-tx_tail)&255u))return;
    /* Publish head only after the entire reply is visible to the ISR. */
    for(i=0;i<n;i++){tx[head]=(uint8_t)message[i];head=(head+1u)&255u;}
    tx_head=head;USART_ITConfig(USART1,USART_IT_TXE,ENABLE);''')
    replace(p,'''    budget=16;
    while(budget-- && tx_tail!=tx_head && USART_GetFlagStatus(USART1,USART_FLAG_TXE)==SET){
        USART_SendData(USART1,tx[tx_tail]);tx_tail=(tx_tail+1u)&255u;
    }''','    /* TXE interrupt drains replies independently of display refresh. */')
    replace(u/'remote_drive.c','R1_GIMBAL_TIM5_20261020','R1_GIMBAL_TIM5_P9_TX_20261021')
build.PREPARE=prepare
if __name__=='__main__':
    build.main();snapshot=build.OUT/'source-snapshot';shutil.copytree(build.WORK/'User',snapshot,dirs_exist_ok=True)
    baseline=build.PROJECT/'知行回路软件/build/r1_gimbal_tim5/source-snapshot'
    changed=[x.relative_to(snapshot).as_posix() for x in snapshot.rglob('*') if x.is_file() and (not (baseline/x.relative_to(snapshot)).exists() or x.read_bytes()!=(baseline/x.relative_to(snapshot)).read_bytes())]
    assert sorted(changed)==['remote_drive.c','vision_uart.c'],changed
    p=build.OUT/'build_result.json';d=json.loads(p.read_text(encoding='utf8'))
    d.update(date='2026-10-21',scope='P9 USART1 TXE IRQ only plus identity; all motor/main/TIM2/TIM5/USB sources unchanged',changed_sources=changed,flash='NOT_RUN',physical_acceptance='NOT_RUN',all_source_sha256={x.relative_to(snapshot).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in snapshot.rglob('*') if x.suffix in ('.c','.h')})
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(d['binary_sha256'])
