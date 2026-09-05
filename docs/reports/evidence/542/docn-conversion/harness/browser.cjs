const {chromium}=require('../../web/node_modules/@playwright/test');
const fs=require('node:fs');
const path=require('node:path');
const label=process.argv[2]||'integration';
const mode=process.argv[3]||'run';
const out=path.resolve('temp/docn-conversion/evidence');
const api='http://127.0.0.1:55479';
async function json(p,method='GET'){const r=await fetch(api+p,{method});if(!r.ok)throw new Error(`${r.status} ${await r.text()}`); return r.json();}
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000},colorScheme:'dark'});
 const page=await context.newPage();
 await page.addInitScript(()=>localStorage.setItem('i18nextLng','en'));
 const network=[]; const errors=[]; const pending=[];
 if(mode==='restore-code') await page.route('**/api/v1/chat/stream',async route=>{
   const response=await route.fetch();
   const raw=await response.text();
   let changes=0;
   const amended=raw.split('\n\n').map(block=>{
     if(!block.startsWith('data: {'))return block;
     const frame=JSON.parse(block.slice(6));
     if(frame.type==='final'){
       if(frame.payload.final_response_payload.code!==undefined)throw new Error('Control requires originally absent code');
       frame.payload.final_response_payload.code='account_conversion_required';changes++;
       return 'data: '+JSON.stringify(frame);
     }
     return block;
   }).join('\n\n');
   if(changes!==1)throw new Error('Control expected exactly one final frame');
   fs.writeFileSync(path.join(out,`${label}-original.sse`),raw);
   await route.fulfill({response,body:amended});
 });
 page.on('pageerror',e=>errors.push(String(e)));
 page.on('response',r=>{if(r.url().includes('/api/v1/'))pending.push((async()=>{let body;try{body=await r.text()}catch(e){body=String(e)}network.push({url:r.url(),status:r.status(),method:r.request().method(),request:r.request().postData(),body});})());});
 try {
 const before=await json('/qa/state');
 await page.goto('http://127.0.0.1:55480/chat?conversation='+before.owner.conversation_id,{waitUntil:'networkidle',timeout:90000});
 console.log('BEFORE READY',await page.getByRole('button',{name:'Run backtest',exact:true}).count());
 if(mode!=='probe'){
 const run=page.getByRole('button',{name:'Run backtest',exact:true}).last();
 await run.waitFor({timeout:20000});
 const streamResponse=page.waitForResponse(r=>r.url().includes('/chat/stream')&&r.request().method()==='POST',{timeout:45000}).catch(()=>null);
 await run.click();
 const response=await Promise.race([streamResponse,page.getByRole('dialog').waitFor({timeout:45000}).then(()=>null)]);
 if(response)await response.finished();
 await page.waitForTimeout(2000);
 console.log('AFTER CLICK\n'+(await page.locator('body').innerText()).slice(-8000));
 }
 await page.screenshot({path:path.join(out,`${label}.png`),fullPage:true});
 await Promise.allSettled(pending);
 const result={label,mode,before,after:await json('/qa/state'),dialogs:await page.getByRole('dialog').allTextContents(),body:await page.locator('body').innerText(),errors,network};
 fs.writeFileSync(path.join(out,`${label}.json`),JSON.stringify(result,null,2));
 console.log('SAVED',label,'DIALOGS',result.dialogs.length,'API',network.filter(n=>n.status>=400).map(n=>[n.url,n.status]));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
