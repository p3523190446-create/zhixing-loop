import {text} from '../core/dom.js';
export function createDiagnostics() {
  return {render(data){
    const d=data.diagnostics;
    text('rawLogInfo',d?(d.ok?(d.active===false?'主控原始记录尚未开始；网页事件独立保存':'原始通信自动记录中'):'日志写入失败：'+d.error):'服务未连接，不能确认日志保存状态');
    text('diagnosticId',d&&d.id||'—');
    text('diagnosticCounts',d?String(d.seq||0)+' 条 / '+String(d.segments||0)+' 段':'—');
    text('diagnosticError',data.error||d&&d.error||'无当前回报错误');
  }};
}
