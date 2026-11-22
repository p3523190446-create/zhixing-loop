/** HTTP adapter only: replace this module when the onboard phone service is ready. */
export function createApi() {
  const base = document.body.dataset.base || location.pathname.replace(/\/(desktop|mobile)\/?$/, '').replace(/\/$/, '');
  let realtime=null;
  const stopPaths=['drive/stop','gimbal/stop','gimbal-follow/stop','line-task/stop','record/stop'];
  function beacon(path,body={}) {
    if(!stopPaths.includes(path))return false;
    const url=base+'/api/'+path,payload=JSON.stringify(body);
    // Chrome 66 rejects application/json Blobs synchronously in sendBeacon.
    // The server accepts text/plain only on these same-origin stop routes.
    try {if(navigator.sendBeacon(url,new Blob([payload],{type:'text/plain;charset=UTF-8'})))return true;}catch(error){}
    try {fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:payload,keepalive:true,cache:'no-store'}).catch(()=>{});}catch(error){}
    return false; // Enqueued delivery still requires the normal MCU stop acknowledgement.
  }
  async function request(path, options = {}, timeout = 3000, binary = false) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(base + '/api/' + path, {cache: 'no-store', ...options, signal: controller.signal});
      if (binary) {
        if(response.status===204)return {unchanged:true,blob:null,seq:null};
        if (!response.ok) throw new Error('画面暂不可用');
        return {blob: await response.blob(), seq: response.headers.get('X-Frame-Seq')};
      }
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '服务未确认操作');
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('等待服务回复超时');
      throw error;
    } finally { clearTimeout(timer); }
  }
  return {
    base,
    attachRealtime: value => {realtime=value;},
    get: (path, timeout) => request(path, {}, timeout),
    post: (path, body = {}, timeout) => realtime&&realtime.active()&&realtime.supports(path)
      ? realtime.request(path,body,timeout)
      : request(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}, timeout),
    image: path => request(path, {}, 2000, true),
    beacon
  };
}
