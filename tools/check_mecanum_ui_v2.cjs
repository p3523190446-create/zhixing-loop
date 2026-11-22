async page => {
  let checks=0;const labels=[];const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const check=(ok,label)=>{checks++;if(!ok)throw Error(label);labels.push(label);};
  const latest=()=>page.evaluate(()=>window.fixture.requests.filter(x=>x.path==='drive/set').map(x=>x.body).pop());
  const clear=()=>page.evaluate(()=>window.fixture.requests=[]);
  await page.waitForFunction(()=>document.documentElement.dataset.uiReady==='true');
  check((await page.locator('#driveTurnPad').getAttribute('aria-disabled'))==='true','rotation locked before arming');
  check(await page.evaluate(()=>!window.fixture.requests.some(x=>x.path==='drive/start')),'no automatic arm');
  await page.locator('#startDrive').click();
  await page.locator('#driveButtons > summary').click();
  const directions={forward:[100,0,0],back:[-100,0,0],left:[0,-100,0],right:[0,100,0],forwardLeft:[100,-100,0],forwardRight:[100,100,0],backLeft:[-100,-100,0],backRight:[-100,100,0],rotateLeft:[0,0,-100],rotateRight:[0,0,100]};
  for(const [name,want] of Object.entries(directions)){
    const el=page.locator('[data-drive-direction='+name+']');await el.scrollIntoViewIfNeeded();const b=await el.boundingBox();await clear();
    await page.mouse.move(b.x+b.width/2,b.y+b.height/2);await page.mouse.down();await page.waitForTimeout(160);const got=await latest();
    check(got&&JSON.stringify([got.throttle,got.strafe,got.turn])===JSON.stringify(want),name+' vector');
    await page.mouse.up();await page.waitForTimeout(30);check(await page.evaluate(()=>window.fixture.requests.some(x=>x.path==='drive/brake')),name+' release brake');
  }
  const pad=page.locator('#driveJoystick'),spin=page.locator('#driveTurnPad');await pad.scrollIntoViewIfNeeded();let b=await pad.boundingBox();await clear();
  await page.mouse.move(b.x+b.width*.65,b.y+b.height*.25);await page.mouse.down();await page.waitForTimeout(160);let got=await latest();
  check(got.throttle>0&&got.strafe>0&&got.turn===0,'arbitrary angle translation without yaw');
  check(got.throttle!==got.strafe&&got.throttle!==100&&got.strafe!==100,'translation is continuous, not eight-direction snapping');await page.mouse.up();await page.waitForTimeout(40);
  await spin.scrollIntoViewIfNeeded();b=await spin.boundingBox();await page.mouse.move(b.x+b.width*.75,b.y+b.height*.5);await page.mouse.down();await page.waitForTimeout(160);got=await latest();
  check(got.turn>0&&got.strafe===0&&got.throttle===0,'rotation pad isolates yaw');await page.mouse.up();await page.waitForTimeout(40);
  await pad.focus();await page.keyboard.down('w');await page.keyboard.down('e');await page.waitForTimeout(160);got=await latest();check(got.throttle===100&&got.turn===100,'keyboard combined movement');
  await page.keyboard.up('e');await page.waitForTimeout(160);got=await latest();check(got.throttle===100&&got.turn===0,'releasing yaw key retains translation');await page.keyboard.up('w');await page.waitForTimeout(40);
  // Real two-contact touchStart; controlled pointer-up checks independent releases.
  await pad.scrollIntoViewIfNeeded();const m=await pad.boundingBox(),r=await spin.boundingBox();
  await page.evaluate(()=>{window.contactIds={};for(const [id,name] of [['driveJoystick','move'],['driveTurnPad','spin']])document.getElementById(id).addEventListener('pointerdown',e=>window.contactIds[name]=e.pointerId);});
  const cdp=await page.context().newCDPSession(page);await cdp.send('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:2});await clear();
  await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:m.x+m.width*.68,y:m.y+m.height*.28,id:11,radiusX:3,radiusY:3},{x:r.x+r.width*.7,y:r.y+r.height*.5,id:22,radiusX:3,radiusY:3}]});
  await page.waitForTimeout(200);got=await latest();check(got&&got.throttle>0&&got.strafe>0&&got.turn>0,'two simultaneous touch contacts combine axes');
  await page.evaluate(()=>document.getElementById('driveJoystick').dispatchEvent(new PointerEvent('pointerup',{pointerId:window.contactIds.move,bubbles:true})));await page.waitForTimeout(160);got=await latest();
  check(got.throttle===0&&got.strafe===0&&got.turn>0,'releasing translation retains held rotation');
  check(!await page.evaluate(()=>window.fixture.requests.some(x=>x.path==='drive/brake')),'one remaining contact does not trigger all-wheel brake');
  await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(60);
  check(await page.evaluate(()=>window.fixture.requests.some(x=>x.path==='drive/brake')),'releasing both contacts brakes');await cdp.send('Emulation.setTouchEmulationEnabled',{enabled:false});await cdp.detach();
  await page.locator('#driveBrake').click();check((await page.locator('#driveIntent').textContent()).includes('零指令'),'center zero resets all axes');
  await page.evaluate(()=>{window.fixture.mecanum=false;window.fixture.render();});
  check(await spin.isHidden(),'ordinary firmware hides rotation pad');check((await page.locator('#driveWestLabel').textContent())==='左转','ordinary firmware retains steering');
  check(await page.locator('#startDrive').isEnabled(),'capability switch revokes session');await page.locator('#startDrive').click();
  await pad.focus();await page.keyboard.down('ArrowRight');await page.waitForTimeout(160);got=await latest();check(got.turn===100&&got.strafe===0,'ordinary joystick does not request strafe');await page.keyboard.up('ArrowRight');await page.locator('#stopDrive').click();
  await page.evaluate(()=>{window.fixture.mecanum=true;window.fixture.render();});await page.locator('#startDrive').click();await page.evaluate(()=>dispatchEvent(new Event('blur')));
  check((await pad.getAttribute('aria-disabled'))==='true','window blur locks controls');check(await page.evaluate(()=>window.fixture.requests.some(x=>x.beacon&&x.path==='drive/stop')),'window blur beacons stop');
  for(const width of [320,390,768,1280]){await page.setViewportSize({width,height:900});await page.waitForTimeout(50);check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'no horizontal overflow '+width);}
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>{document.getElementById('driveTools').open=false;document.getElementById('driveButtons').open=false;document.querySelector('.mecanum-help').open=true;document.getElementById('controlDock').style.maxHeight='none';});
  await page.locator('#driveCard').screenshot({path:'C:/Users/panyuanhao/Documents/ChatGPT/新生嵌入式比赛(知行回路)/output/playwright/mecanum-controls-mobile.png'});
  await page.setViewportSize({width:1280,height:1000});await page.locator('#driveCard').screenshot({path:'C:/Users/panyuanhao/Documents/ChatGPT/新生嵌入式比赛(知行回路)/output/playwright/mecanum-controls-desktop.png'});
  check(errors.length===0,'no uncaught JS errors');
  const report={result:'PASS',checks,hardware_io:false,scope:'Chromium fake API; includes two-contact touch start and controlled independent pointer release',labels,errors};
  await page.evaluate(report=>window.mecanumUiReport=report,report);return report;
}
