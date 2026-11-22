/** One request/decode at a time; missed deadlines never accumulate work. */
export function createFramePump(frame, active, interval, clock = {
  now: () => performance.now(),
  set: (callback, delay) => setTimeout(callback, delay),
  clear: timer => clearTimeout(timer)
}) {
  let timer=null,closed=false,due=null;
  async function tick() {
    if(closed)return;
    if(!active())due=null;
    else {
      const now=clock.now();
      if(due===null)due=now;
      if(now>=due){
        due=Math.max(due+interval(),now);
        try{await frame();}catch(error){/* The owner displays frame errors. */}
      }
    }
    if(!closed)timer=clock.set(tick,due===null?100:Math.max(1,due-clock.now()));
  }
  timer=clock.set(tick,0);
  return {close(){closed=true;clock.clear(timer);}};
}
