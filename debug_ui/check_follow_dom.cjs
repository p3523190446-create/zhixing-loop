/** jsdom only: no browser launched, no network or actual controller requests. */
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {JSDOM}=require(path.join(process.env.USERPROFILE,'.cache/zhixing-follow-dom/node_modules/jsdom'));
(async()=>{
 const dom=new JSDOM(fs.readFileSync(path.join(__dirname,'index.html'),'utf8'),{url:'http://fixture.invalid/',runScripts:'outside-only',pretendToBeVisual:true});
 try{
  const run=async(file,source)=>dom.window.eval(fs.readFileSync(path.join(__dirname,'checks',file),'utf8')+';'+
   (file.startsWith('gimbal_follow')?'gimbalFollowBrowserFixture':'gimbalPrepareBrowserFixture')+'('+JSON.stringify(source)+')');
  const follow=await run('gimbal_follow_browser_fixture.js',fs.readFileSync(path.join(__dirname,'assets/features/gimbal-follow.js'),'utf8'));
  const prepare=await run('gimbal_prepare_browser_fixture.js',fs.readFileSync(path.join(__dirname,'assets/features/gimbal.js'),'utf8'));
  assert(follow.manual.heartbeat&&follow.savedCenter.enabled&&follow.savedCenter.heartbeat);
  assert(!follow.manual.late_poll_during_start&&!follow.savedCenter.late_poll_during_start);
  for(const r of prepare.slice(0,2)){assert(r.offered&&r.start_count===1&&r.profile_unchanged);}
  assert(!prepare[2].ready&&prepare[2].start_count===0);
  assert(!prepare[3].offered&&prepare[3].stop_count===1);
  assert(!prepare[4].offered&&prepare[4].stop_count===0);
  const result={follow,prepare,software_only:true,actual_motion:false};
  fs.writeFileSync(path.join(process.env.ZX_GIMBAL_CHECK_OUT,'follow-dom-checks.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
 }finally{dom.window.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
