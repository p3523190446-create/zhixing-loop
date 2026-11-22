async page => {
  let checks=0;
  const check=(ok,label)=>{checks++;if(!ok)throw new Error(label);};
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.waitForFunction(()=>document.documentElement.dataset.uiReady==='true');
  await page.locator('#startDrive').click();
  const directions={forward:[100,0,0],back:[-100,0,0],left:[0,-100,0],right:[0,100,0],forwardLeft:[100,-100,0],forwardRight:[100,100,0],backLeft:[-100,-100,0],backRight:[-100,100,0],rotateLeft:[0,0,-100],rotateRight:[0,0,100]};
  for(const [name,expected] of Object.entries(directions)){
    const node=page.locator('[data-drive-direction='+name+']');await node.scrollIntoViewIfNeeded();const box=await node.boundingBox();
    await page.evaluate(()=>window.fixture.requests=[]);
    await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();
    await page.waitForTimeout(160);
    const sent=await page.evaluate(()=>window.fixture.requests.filter(x=>x.path==='drive/set').map(x=>x.body).pop());
    check(sent&&JSON.stringify([sent.throttle,sent.strafe,sent.turn])===JSON.stringify(expected),name+' correct vector');
    await page.mouse.up();await page.waitForTimeout(30);
    check(await page.evaluate(()=>window.fixture.requests.some(x=>x.path==='drive/brake')),name+' release brake');
    check((await page.locator('#driveTarget').textContent())==='前后 0 / 横移 0 / 旋转 0',name+' UI reset');
  }
  const pad=page.locator('#driveJoystick');await pad.scrollIntoViewIfNeeded();await pad.focus();
  await page.keyboard.down('ArrowUp');await page.keyboard.down('ArrowRight');await page.keyboard.down('e');await page.waitForTimeout(160);
  let sent=await page.evaluate(()=>window.fixture.requests.filter(x=>x.path==='drive/set').map(x=>x.body).pop());
  check(sent.throttle===100&&sent.strafe===100&&sent.turn===100,'combined translation and rotation');
  await page.keyboard.up('ArrowUp');await page.keyboard.up('ArrowRight');await page.keyboard.up('e');
  await page.waitForTimeout(30);check((await pad.getAttribute('aria-disabled'))==='false','release keeps zero session');
  const box=await pad.boundingBox();await page.mouse.move(box.x+box.width*.85,box.y+box.height*.5);await page.mouse.down();await page.waitForTimeout(160);
  sent=await page.evaluate(()=>window.fixture.requests.filter(x=>x.path==='drive/set').map(x=>x.body).pop());
  check(sent.strafe>0&&sent.throttle===0&&sent.turn===0,'stick horizontal means strafe');await page.mouse.up();
  await page.evaluate(()=>{window.fixture.mecanum=false;window.fixture.render();});
  check(await page.locator('[data-mecanum-only]').isHidden(),'old firmware hides rotation extras');
  check((await page.locator('#driveWestLabel').textContent())==='左转','old firmware retains turn labels');
  check((await page.locator('#startDrive').isEnabled()),'capability change revokes session');
  await page.locator('#startDrive').click();await pad.focus();await page.keyboard.down('ArrowRight');await page.waitForTimeout(160);
  sent=await page.evaluate(()=>window.fixture.requests.filter(x=>x.path==='drive/set').map(x=>x.body).pop());
  check(sent.strafe===0&&sent.turn===100,'old firmware does not receive strafe');await page.keyboard.up('ArrowRight');
  await page.locator('#stopDrive').click();await page.evaluate(()=>{window.fixture.mecanum=true;window.fixture.render();});
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(200);
  check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile has no horizontal overflow');
  await page.screenshot({path:'C:/Users/panyuanhao/Documents/ChatGPT/新生嵌入式比赛 2/output/playwright/mecanum-mobile.png',fullPage:true});
  await page.setViewportSize({width:1280,height:900});await page.screenshot({path:'C:/Users/panyuanhao/Documents/ChatGPT/新生嵌入式比赛 2/output/playwright/mecanum-desktop.png',fullPage:true});
  check(errors.length===0,'no uncaught JS errors');
  console.log(JSON.stringify({result:'PASS',checks,hardware_io:false,scope:'Desktop Chromium, fake in-browser API; not phone/USB/ground acceptance',errors}));
}
