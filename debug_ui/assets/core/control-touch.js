/** Keep held controls in the pointer stream instead of native text/callout UI. */
const protectedControls=new WeakSet();
export function protectHoldControl(node) {
  if(!node||protectedControls.has(node))return;
  protectedControls.add(node);
  const cancel=event=>event.preventDefault();
  ['contextmenu','selectstart','dragstart'].forEach(name=>node.addEventListener(name,cancel));
  const touch=event=>{
    if(!node.disabled&&node.getAttribute('aria-disabled')!=='true')event.preventDefault();
  };
  node.addEventListener('touchstart',touch,{passive:false});
  node.addEventListener('touchmove',touch,{passive:false});
}
