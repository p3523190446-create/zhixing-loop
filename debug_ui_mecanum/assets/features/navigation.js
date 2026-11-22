import {$, all} from '../core/dom.js';
export function createNavigation(onShow) {
  const route = location.pathname.replace(/\/$/, '').split('/').pop();
  const mobile = route === 'mobile';
  document.body.classList.toggle('mobile-preview', mobile && innerWidth > 760);
  $('viewLabel').textContent = route === 'desktop' ? '电脑版 · 窄屏自动重排' : mobile ? '手机版' : '自动适配';
  function show(tab, scroll = false) {
    if (!['live','telemetry','records'].includes(tab)) tab = 'live';
    all('[data-panel]').forEach(panel => panel.hidden = panel.dataset.panel !== tab);
    all('[data-tab]').forEach(button => button.setAttribute('aria-selected', String(button.dataset.tab === tab)));
    history.replaceState(null, '', '#' + tab);
    onShow(tab);
    if (scroll) window.scrollTo({top:0,behavior:'auto'});
  }
  all('[data-tab]').forEach(button => button.addEventListener('click', () => show(button.dataset.tab, true)));
  document.querySelector('.brand').addEventListener('click', event => {event.preventDefault();show('live', true);});
  window.addEventListener('hashchange', () => show(location.hash.slice(1)));
  window.addEventListener('resize', () => document.body.classList.toggle('mobile-preview', mobile && innerWidth > 760));
  show(location.hash.slice(1));
  return {show};
}
