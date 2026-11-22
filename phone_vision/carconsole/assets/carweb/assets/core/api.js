/** HTTP adapter only: replace this module when the onboard phone service is ready. */
export function createApi() {
  const base = document.body.dataset.base || location.pathname.replace(/\/(desktop|mobile)\/?$/, '').replace(/\/$/, '');
  async function request(path, options = {}, timeout = 3000, binary = false) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(base + '/api/' + path, {cache: 'no-store', ...options, signal: controller.signal});
      if (binary) {
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
    get: (path, timeout) => request(path, {}, timeout),
    post: (path, body = {}, timeout) => request(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}, timeout),
    image: path => request(path, {}, 2000, true),
    beacon: path => navigator.sendBeacon(base + '/api/' + path, new Blob(['{}'], {type:'application/json'}))
  };
}
