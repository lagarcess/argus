// Candidate acceptance uses real API responses. There is no route interception.
const {chromium,expect}=require('../../web/node_modules/@playwright/test');
const fs=require('node:fs');
const path=require('node:path');
const qaLanguage=process.argv[2]||'en';
const candidate=path.resolve('temp/542-conversion-fix/candidate');
const out=path.resolve('temp/542-public-signup/evidence');
const copy=require(path.join(candidate,'web/public/locales',qaLanguage,'common.json'));
const runLabel=copy.chat.confirmation.actions.run_backtest;
const api='http://127.0.0.1:55479';
async function json(p,method='GET'){const r=await fetch(api+p,{method});if(!r.ok)throw new Error(`${p}: ${r.status} ${await r.text()}`);return r.json();}
(async()=>{
 const browser=await chromium.launch({headless:true});
 const captures=[];
 async function clickRun(label,mode){
  const context=await browser.newContext({viewport:{width:1440,height:1000},colorScheme:'dark'});
  const page=await context.newPage();
  await page.addInitScript(language=>localStorage.setItem('i18nextLng',language),qaLanguage);
  const network=[],errors=[],pending=[];
  page.on('pageerror',e=>errors.push(String(e)));
  page.on('response',r=>{if(r.url().includes('/api/v1/'))pending.push((async()=>{
   let body;try{body=await r.text()}catch(e){body=String(e)}
   network.push({url:r.url(),status:r.status(),method:r.request().method(),request:r.request().postData(),body});
  })());});
  try{
   const before=await json('/qa/state');
   await page.goto('http://127.0.0.1:55480/chat?conversation='+before.owner.conversation_id,{waitUntil:'networkidle',timeout:60000});
   const button=page.getByRole('button',{name:runLabel,exact:true}).last();
   await expect(button).toBeVisible();
   let response;
   if(mode==='same-day'){
    await button.click();
   }else{
    [response]=await Promise.all([page.waitForResponse(r=>r.url().includes('/chat/stream')&&r.request().method()==='POST'),button.click()]);
    await response.finished();
   }
   if(mode==='completed'){
    await expect.poll(async()=>(await json('/qa/state')).runs.length).toBe(before.runs.length+1);
    await expect(page.getByRole('dialog')).toHaveCount(0);
   }else{
    const dialog=page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    const key=mode==='same-day'?'simulation_limit_reset':'simulation_workspace_limit_reset';
    for(const part of copy.guest.conversion[key].split('{{date}}')) await expect(dialog).toContainText(part.trim());
    await expect(dialog.getByRole('heading',{name:copy.guest.conversion.create_title,exact:true})).toBeVisible();
    await expect(dialog.getByRole('button',{name:copy.auth.signup.submit,exact:true})).toBeVisible();
    await expect(dialog.locator('input[type=password]')).toBeVisible();
    await expect(dialog).not.toContainText(copy.auth.access_request.title);
    await expect(dialog).not.toContainText(copy.auth.access_request.description);
   }
   await page.waitForTimeout(500);
   await page.screenshot({path:path.join(out,`${label}.png`),fullPage:true});
   await Promise.allSettled(pending);
   const after=await json('/qa/state');
   const streams=network.filter(n=>n.url.includes('/chat/stream'));
   if(mode==='same-day')expect(streams).toHaveLength(0);
   if(mode==='next-day'){
    expect(before.jobs).toEqual([]);expect(before.runs).toEqual([]);
    expect(after.jobs).toHaveLength(1);expect(after.runs).toEqual([]);
    expect(after.jobs[0][2]).toBe('account_conversion_required');
    expect(after.workspace_usage).toEqual(before.workspace_usage);
    expect(streams).toHaveLength(1);
    const frames=streams[0].body.split('\n\n').filter(f=>f.startsWith('data: {')).map(f=>JSON.parse(f.slice(6)));
    expect(frames.find(f=>f.type==='final').payload.final_response_payload.code).toBe('account_conversion_required');
   }
   expect(errors).toEqual([]);
   const accountResponses=network.filter(n=>new URL(n.url).pathname==='/api/v1/me'&&n.status===200).map(n=>JSON.parse(n.body));
   expect(accountResponses.length).toBeGreaterThan(0);
   for(const account of accountResponses)expect(account.public_account_access_enabled).toBe(true);
   const evidence={label,mode,language:qaLanguage,before,after,dialogs:await page.getByRole('dialog').allTextContents(),body:await page.locator('body').innerText(),errors,accountResponses,network};
   fs.writeFileSync(path.join(out,`${label}.json`),JSON.stringify(evidence,null,2));
   captures.push({label,mode,modal:evidence.dialogs.length===1,stream_requests:streams.length,run_count:after.runs.length,job_count:after.jobs.length,counter:after.workspace_usage});
   console.log('PASS',label,JSON.stringify(captures.at(-1)));
  }finally{await context.close()}
 }
 try{
  const account=await json('/api/v1/me');
  expect(account.public_account_access_enabled).toBe(true);expect(account.account_kind).toBe('guest');expect(account.guest.simulation_limit).toBe(2);
  for(let run=1;run<=account.guest.simulation_limit;run++){
   await json('/qa/confirmation','POST');
   await clickRun(`${qaLanguage}-run${run}`,'completed');
  }
  expect((await json('/qa/state')).workspace_usage).toEqual([['backtest_runs','guest_session',2,2]]);
  await json('/qa/confirmation','POST');
  await clickRun(`${qaLanguage}-same-day`,'same-day');
  await json('/qa/day-rollover','POST');
  await json('/qa/start-over','POST');
  await json('/qa/confirmation','POST');
  await clickRun(`${qaLanguage}-next-day`,'next-day');
  fs.writeFileSync(path.join(out,`${qaLanguage}-summary.json`),JSON.stringify(captures,null,2));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
