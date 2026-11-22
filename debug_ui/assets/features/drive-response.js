/* Velocity-input slew limiting, following WPILib's joystick filter approach.
 * Normalized input units only: not an estimate of traction or vehicle speed. */
const bound=(v,n)=>Math.max(-n,Math.min(n,v));
export function softAxis(value){
  const v=bound(Number(value)||0,100),a=Math.abs(v);
  if(a<=12)return 0;
  const x=(a-12)/88;
  return Math.sign(v)*100*(.55*x+.45*x*x*x);
}
export function createDriveResponse(){
  let values=[0,0,0],last=0;
  return {
    reset(now=0){values=[0,0,0];last=now;},
    step(input,now,soft){
      const dt=Math.max(0,Math.min(.2,(now-last)/1000));last=now;
      if(!soft){values=input.slice();return values.slice();}
      const wanted=[softAxis(input[0]),softAxis(input[1]),softAxis(input[2])*.55];
      values=values.map((v,i)=>{
        // Releasing either axis applies zero immediately, even with the other held.
        if(wanted[i]===0)return 0;
        const target=v*wanted[i]<0?0:wanted[i];
        return v+bound(target-v,(i===2?90:140)*dt);
      });
      return values.map(v=>Math.round(v));
    }
  };
}
