import {$, number} from '../core/dom.js';
export function createDistanceChart() {
  const rows = [];
  function push(value) { rows.push(value); if (rows.length > 60) rows.shift(); draw(); }
  function gap() { if (rows.length && rows[rows.length-1] !== null) push(null); }
  function draw() {
    const canvas = $('plot'), width = canvas.clientWidth, height = 180;
    if (!width) return;
    const ratio = Math.min(devicePixelRatio || 1, 3);
    canvas.width = width * ratio; canvas.height = height * ratio;
    const ctx = canvas.getContext('2d'); ctx.scale(ratio,ratio);
    ctx.strokeStyle = '#2b3e41'; ctx.fillStyle = '#9eafae'; ctx.font = '10px system-ui';
    const valid = rows.filter(v => v != null && Number.isFinite(v));
    const max = Math.max(100, ...valid);
    for (let i = 0; i < 4; i++) {
      const y = 16 + i * 45; ctx.beginPath();ctx.moveTo(34,y);ctx.lineTo(width,y);ctx.stroke();
      ctx.fillText(number((max * (3-i)/3)/10,0), 0, y+4);
    }
    ctx.strokeStyle='#a9e4c3';ctx.lineWidth=2;ctx.beginPath();let open=false;
    rows.forEach((v,i)=>{if(v==null){open=false;return;}const x=34+i*(width-40)/59,y=151-v/max*135;if(open)ctx.lineTo(x,y);else ctx.moveTo(x,y);open=true;});ctx.stroke();
    $('plotNote').textContent = valid.length ? '单位 cm · 中断处不连线 · 窗口最高 '+number(max/10)+' cm' : '等待有效距离';
  }
  addEventListener('resize', draw);
  return {push, gap, draw};
}
