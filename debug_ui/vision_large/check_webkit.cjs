/** Safari-engine check; not a claim of acceptance on the user's actual iPad. */
const path=require('node:path'),fs=require('node:fs');
const playwright=require(path.resolve(path.dirname(process.execPath),'../node_modules/playwright'));
(async()=>{
 const browser=await playwright.webkit.launch({headless:true,executablePath:process.argv[3]||undefined});
 try{
  const context=await browser.newContext({viewport:{width:768,height:1024}}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.argv[2]);await page.waitForTimeout(3000);
  const report=await page.evaluate(()=>({ready:document.documentElement.getAttribute('data-ui-ready'),endpoint:document.getElementById('vlmEndpoint')&&document.getElementById('vlmEndpoint').value,state:document.getElementById('vlmState')&&document.getElementById('vlmState').textContent,message:document.getElementById('vlmMessage')&&document.getElementById('vlmMessage').textContent}));
  console.log(JSON.stringify({engine:'WebKit',...report,errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
