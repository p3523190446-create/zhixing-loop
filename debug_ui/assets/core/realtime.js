/** Long-lived latest-status transport. No offline queue, replay or automatic arm. */
export function createRealtime({base,onStatus,onMode,onLatency,onFailure}) {
  let socket=null,generation=0,closed=false,retry=null,heartbeat=null,attempts=0,lastReceive=0,sequence=0;
  const pending=new Map(),pings=new Map(),rtts=[];
  const allowed=new Set(['gimbal/start','gimbal/set','gimbal/center','gimbal/heartbeat','gimbal/stop']);
  const active=()=>socket&&socket.readyState===WebSocket.OPEN;
  function rejectPending(message){for(const job of pending.values()){clearTimeout(job.timer);job.reject(new Error(message));}pending.clear();pings.clear();}
  function clearTimers(){clearInterval(heartbeat);heartbeat=null;}
  function connect(){
    if(closed||document.hidden)return;
    const current=++generation;let statusSeq=0;
    const candidate=new WebSocket(location.origin.replace(/^http/,'ws')+base+'/api/realtime');socket=candidate;
    const connectTimer=setTimeout(()=>candidate.close(),4000);
    candidate.onopen=()=>{if(current!==generation||closed){candidate.close();return;}clearTimeout(connectTimer);attempts=0;lastReceive=performance.now();onMode('WebSocket · 实时推送');
      heartbeat=setInterval(()=>{if(current!==generation||!active())return;if(performance.now()-lastReceive>3500){candidate.close();return;}
        const id='p'+(++sequence);pings.set(id,performance.now());for(const[key,at]of pings)if(performance.now()-at>3500)pings.delete(key);candidate.send(JSON.stringify({type:'ping',id}));
      },1000);
    };
    candidate.onmessage=event=>{
      if(current!==generation||closed)return;
      try{const message=JSON.parse(event.data);lastReceive=performance.now();
        if(message.type==='status'){if(!Number.isSafeInteger(message.seq)||message.seq<=statusSeq||!message.data||typeof message.data!=='object')throw Error('推送状态格式错误');statusSeq=message.seq;onStatus(message.data);}
        else if(message.type==='pong'){const began=pings.get(message.id);if(began!=null){pings.delete(message.id);rtts.push(performance.now()-began);if(rtts.length>60)rtts.shift();const sorted=[...rtts].sort((a,b)=>a-b);onLatency({rtt_ms:rtts[rtts.length-1],p95_ms:sorted[Math.ceil(sorted.length*.95)-1],samples:rtts.length});}}
        else if(message.type==='reply'){const job=pending.get(message.id);if(job){pending.delete(message.id);clearTimeout(job.timer);if(message.ok)job.resolve(message.data);else job.reject(Error(message.error||'主控未确认操作'));}}
      }catch(error){onFailure(error.message);candidate.close();}
    };
    candidate.onerror=()=>candidate.close();
    candidate.onclose=()=>{clearTimeout(connectTimer);if(current!==generation)return;clearTimers();socket=null;rejectPending('长连接中断，操作结果未确认；不会自动重发');onMode('HTTP · 轮询回退');onLatency(null);onFailure('实时通道已断开，等待读取新状态。');if(!closed&&!document.hidden)retry=setTimeout(connect,Math.min(5000,500*2**attempts++));};
  }
  function request(path,body,timeout=2500){
    if(!active()||!allowed.has(path))return Promise.reject(Error('实时通道未就绪'));
    if(pending.size>=4)return Promise.reject(Error('等待回执过多，请停止调整'));
    const id='c'+(++sequence),candidate=socket;
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{pending.delete(id);reject(Error('主控回执超时；不会自动重发'));},timeout);
      pending.set(id,{resolve,reject,timer});
      try{candidate.send(JSON.stringify({type:'command',id,path,body}));}catch(error){pending.delete(id);clearTimeout(timer);reject(error);}
    });
  }
  function suspend(){generation++;clearTimeout(retry);clearTimers();rejectPending('页面离开，未确认操作不会重发');if(socket)socket.close();socket=null;onMode('HTTP · 轮询回退');onLatency(null);}
  return {start:connect,active,supports:path=>allowed.has(path),request,
    suspend,resume(){if(!closed&&!active())connect();},destroy(){closed=true;suspend();}};
}
