// The K99's WebView66 predates replaceChildren; keep real record-list refresh usable.
if (!Element.prototype.replaceChildren) {
  Element.prototype.replaceChildren = function (...children) {
    while (this.firstChild) this.removeChild(this.firstChild);
    children.forEach(child => this.appendChild(child instanceof Node ? child : document.createTextNode(String(child))));
  };
}
export const $ = id => document.getElementById(id);
export const all = selector => Array.from(document.querySelectorAll(selector));
export function text(id, value) { $(id).textContent = value; }
export function badge(id, value, style = '') { text(id, value); $(id).className = 'badge ' + style; }
export function number(value, digits = 1) { return value == null || !Number.isFinite(Number(value)) ? '—' : Number(value).toFixed(digits); }
export function duration(value) {
  if (value == null || !Number.isFinite(Number(value))) return '—';
  const n = Math.max(0, Math.floor(value));
  return [Math.floor(n / 3600), Math.floor(n / 60) % 60, n % 60].map(v => String(v).padStart(2,'0')).join(':');
}
export function clamp(value, limit) { return Math.round(Math.max(-limit, Math.min(limit, Number(value) || 0))); }
