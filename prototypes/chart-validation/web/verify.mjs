import { chromium, webkit } from '../../../web/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import os from 'node:os';
import { createHash } from 'node:crypto';
import { segments, formattedValue, formattedDate } from './model.mjs';
const evidence = new URL('../../../docs/reports/evidence/chart-validation/web/',import.meta.url);
await mkdir(evidence,{recursive:true});
const fixture=JSON.parse(await readFile(new URL('../fixtures/series.json',import.meta.url)));
const report={sourceHead:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),timestamp:new Date().toISOString(),host:`${os.platform()} ${os.release()} ${os.arch()}`,node:process.version,library:JSON.parse(await readFile(new URL('../../../web/node_modules/lightweight-charts/package.json',import.meta.url))).version,fixtureSha256:createHash('sha256').update(await readFile(new URL('../fixtures/series.json',import.meta.url))).digest('hex'),device:'Desktop browser and touch-enabled viewport emulation; no physical device',browsers:[]};
for(const [name,engine] of [['chromium',chromium],['webkit',webkit]]) {
  const browser=await engine.launch({headless:true});
  const context=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:2,isMobile:true,hasTouch:true,timezoneId:'Pacific/Honolulu'});
  const page=await context.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:4179');
  await page.waitForFunction(()=>window.chartPrototype?.metrics.renders.length>0);
  const results=[];
  for(const scenario of fixture.cases) {
    await page.selectOption('#scenario',scenario.id);
    await page.waitForTimeout(80);
    assert.equal(await page.locator('#readout').getAttribute('data-index'),'');
    assert.equal(await page.evaluate(()=>window.chartPrototype.state.segmentCount),segments(scenario.points,'actual').length+segments(scenario.points,'projected').length);
    if(!scenario.points.length) {
      assert.equal(await page.locator('#next').isDisabled(),true);
      assert.equal(await page.locator('#previous').isDisabled(),true);
    } else {
      await page.click('#next');
      assert.equal(await page.locator('#readout').getAttribute('data-date'),scenario.points[0].time);
      assert.equal(await page.locator('#previous').isDisabled(),true);
      await page.click('#reset');
      await page.click('#previous');
      assert.equal(await page.locator('#readout').getAttribute('data-date'),scenario.points.at(-1).time);
      assert.equal(await page.locator('#next').isDisabled(),true);
      await page.selectOption('#locale','es-419');
      for(const key of ['actual','projected','contribution']) {
        assert.ok((await page.locator(`[data-field=${key}]`).innerText()).includes(formattedValue(scenario.points.at(-1)[key],scenario.currency,'es-419')));
      }
      assert.ok((await page.locator('#readout').innerText()).includes(formattedDate(scenario.points.at(-1).time,'es-419')));
      await page.selectOption('#locale','en');
    }
    results.push(`${scenario.id}: endpoints, reset, independent values, segment structure, formatting pass`);
  }
  const scenario=fixture.cases.find(c=>c.id==='stress');
  await page.selectOption('#scenario',scenario.id);
  await page.locator('#scrub').scrollIntoViewIfNeeded();
  await page.waitForTimeout(100);
  const box=await page.locator('#scrub').boundingBox();
  const coords=await page.evaluate(()=>Array.from({length:window.chartPrototype.state.points},(_,i)=>window.chartPrototype.coordinate(i)));
  assert.ok(coords.every(Number.isFinite));
  const y=box.y+box.height/2;
  const gapIndex=scenario.points.findIndex(p=>p.actual===null && p.projected===null);
  await page.mouse.click(box.x+coords[gapIndex],y);
  assert.equal(await page.locator('#readout').getAttribute('data-index'),String(gapIndex));
  assert.ok((await page.locator('[data-field=actual]').innerText()).includes('No data'));
  assert.ok((await page.locator('[data-field=projected]').innerText()).includes('No data'));
  await page.screenshot({path:new URL(`${name}-missing-point.png`,evidence).pathname,fullPage:true});
  // Mouse scrubbing exercises the same pointer lifecycle in both browser engines.
  await page.mouse.move(box.x+coords[0],y);await page.mouse.down();
  await page.mouse.move(box.x+coords.at(-1),y,{steps:10});await page.mouse.up();
  assert.equal(await page.locator('#readout').getAttribute('data-date'),scenario.points.at(-1).time);
  await page.mouse.move(box.x+coords.at(-1),y);await page.mouse.down();
  await page.mouse.move(box.x-2,y,{steps:10});await page.mouse.up();
  assert.equal(await page.locator('#readout').getAttribute('data-date'),scenario.points[0].time);
  // Every fixture row, including explicit missing rows, is available without dragging.
  for(let i=1;i<scenario.points.length;i++) {
    await page.click('#next');
    assert.equal(await page.locator('#readout').getAttribute('data-date'),scenario.points[i].time);
    for(const key of ['actual','projected','contribution']) assert.ok((await page.locator(`[data-field=${key}]`).innerText()).includes(formattedValue(scenario.points[i][key],scenario.currency,'en')));
  }
  results.push('mouse release retains; horizontal endpoints clamp; every stress row accessible including gaps');
  await page.selectOption('#theme','light');
  assert.equal(await page.locator('html').getAttribute('data-dark'),'false');
  await page.screenshot({path:new URL(`${name}-light-en.png`,evidence).pathname,fullPage:true});
  await page.selectOption('#locale','es-419');await page.selectOption('#theme','dark');
  assert.equal(await page.locator('html').getAttribute('data-dark'),'true');
  await page.screenshot({path:new URL(`${name}-dark-es-419.png`,evidence).pathname,fullPage:true});
  await page.selectOption('#theme','system');
  await page.emulateMedia({colorScheme:'light'});await page.waitForFunction(()=>document.documentElement.dataset.dark==='false');assert.equal(await page.locator('html').getAttribute('data-dark'),'false');
  await page.emulateMedia({colorScheme:'dark'});await page.waitForFunction(()=>document.documentElement.dataset.dark==='true');assert.equal(await page.locator('html').getAttribute('data-dark'),'true');
  await page.selectOption('#locale','en');
  if(name==='chromium') {
    const cdp=await context.newCDPSession(page);
    await page.locator('#scrub').scrollIntoViewIfNeeded();
    const b=await page.locator('#scrub').boundingBox();
    const touch=async(type,x,y)=>cdp.send('Input.dispatchTouchEvent',{type,touchPoints:type==='touchEnd'||type==='touchCancel'?[]:[{x,y,radiusX:1,radiusY:1}]});
    const start=b.x+coords[0],end=b.x+coords.at(-1),ty=b.y+100;
    await page.click('#reset');await page.locator('#scrub').scrollIntoViewIfNeeded();
    await touch('touchStart',start,ty);await touch('touchMove',end,ty);await touch('touchEnd');
    assert.equal(await page.locator('#readout').getAttribute('data-date'),scenario.points.at(-1).time);
    await touch('touchStart',end,ty);await touch('touchMove',start,ty);await touch('touchCancel');
    assert.equal(await page.locator('#readout').getAttribute('data-date'),scenario.points.at(-1).time);
    const before=await page.evaluate(()=>scrollY);
    await touch('touchStart',b.x+100,ty+80);
    for(let i=1;i<=6;i++){await touch('touchMove',b.x+100,ty+80-i*20);await page.waitForTimeout(20);}
    await touch('touchEnd');await page.waitForTimeout(120);
    const after=await page.evaluate(()=>scrollY);
    assert.ok(after>before+20,`vertical scroll: ${before} -> ${after}`);
    assert.equal(await page.locator('#readout').getAttribute('data-date'),scenario.points.at(-1).time);
    results.push(`CDP touch: horizontal release retained; cancellation restored; vertical scroll ${before} -> ${after}px preserved selection`);
  } else results.push('WebKit touch cancellation/vertical gestures not automated: Chromium touch evidence only');
  // Keyboard access: reset then focus Next and activate it with Enter.
  await page.click('#reset');await page.focus('#next');await page.keyboard.press('Enter');
  assert.equal(await page.locator('#readout').getAttribute('data-index'),'0');
  const frameTimes=await page.evaluate(async()=>{
    const values=[];let last=performance.now();
    for(let i=0;i<120;i++) await new Promise(resolve=>requestAnimationFrame(now=>{values.push(now-last);last=now;resolve();}));
    return values;
  });
  const long=fixture.cases.find(c=>c.points.length===2000);
  for(let i=0;i<8;i++){await page.selectOption('#scenario','empty');await page.selectOption('#scenario',long.id);await page.waitForTimeout(100);}
  await page.locator('#scrub').scrollIntoViewIfNeeded();
  const longBox=await page.locator('#scrub').boundingBox();
  await page.mouse.move(longBox.x+5,longBox.y+100);await page.mouse.down();
  await page.mouse.move(longBox.x+longBox.width-5,longBox.y+100,{steps:100});await page.mouse.up();
  const metrics=await page.evaluate(()=>window.chartPrototype.metrics);
  const percentile=(arr,p)=>[...arr].sort((a,b)=>a-b)[Math.min(arr.length-1,Math.floor(arr.length*p))];
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  report.browsers.push({name,version:browser.version(),viewport:'390x844 @2x',results,renderLongMs:metrics.renders.filter(v=>v.scenario===long.id).map(v=>v.ms),readoutMs:{samples:metrics.selections.length,p50:percentile(metrics.selections,.5),p95:percentile(metrics.selections,.95),max:Math.max(...metrics.selections)},idleFrameMs:{samples:frameTimes.length,p50:percentile(frameTimes,.5),p95:percentile(frameTimes,.95)},pageErrors:errors});
  assert.deepEqual(errors,[]);
  await page.setViewportSize({width:1280,height:800});await page.screenshot({path:new URL(`${name}-desktop-long.png`,evidence).pathname,fullPage:true});
  await browser.close();
}
await writeFile(new URL('measurements.json',evidence),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
