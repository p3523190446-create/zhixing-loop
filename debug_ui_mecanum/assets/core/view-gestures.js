/** Fixed-scale vehicle controls: allow scrolling, suppress browser zoom gestures. */
const cancel=event=>event.preventDefault();
['gesturestart','gesturechange','gestureend','dblclick'].forEach(name=>
  document.addEventListener(name,cancel,{passive:false}));
document.addEventListener('touchmove',event=>{
  if(event.touches&&event.touches.length>1)event.preventDefault();
},{passive:false});
