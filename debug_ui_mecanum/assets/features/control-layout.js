import {$,all} from '../core/dom.js';

/** Keep either set of controls beside the same camera, without auto arming. */
export function createControlLayout({drive,gimbal}) {
  let selected='drive';
  const dock=$('controlDock'),buttons=all('[data-control-mode]');
  function select(mode){
    if(!['drive','gimbal'].includes(mode))return;
    if(mode!==selected){
      if(selected==='drive')drive.leave();else gimbal.leave();
    }
    selected=mode;
    for(const name of ['drive','gimbal']){
      const card=$(name+'Card'),active=name===mode;
      card.open=active;card.hidden=!active;
    }
    buttons.forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.controlMode===mode)));
    dock.scrollTop=0;
  }
  buttons.forEach(button=>button.addEventListener('click',()=>select(button.dataset.controlMode)));
  function size(){
    if(innerWidth<=760){dock.style.removeProperty('max-height');return;}
    // Reserve the actual header height, including any connection warning.
    const top=dock.getBoundingClientRect().top+scrollY;
    dock.style.maxHeight=Math.max(280,innerHeight-top-12)+'px';
  }
  window.addEventListener('resize',size);
  if(typeof ResizeObserver!=='undefined'){
    const observer=new ResizeObserver(size);
    [document.querySelector('.app-header'),document.querySelector('.tabs'),$('notice'),$('demoNotice')].forEach(n=>observer.observe(n));
  }
  select(selected);requestAnimationFrame(size);
  return {select,refresh:size};
}
