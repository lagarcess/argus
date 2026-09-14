// Adapted from grounded-math/drivers/walk.mjs: real auth and real composer.
import {createRequire} from 'node:module';
import {readFileSync,writeFileSync,mkdirSync,existsSync,readdirSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {randomBytes} from 'node:crypto';
import {fileURLToPath} from 'node:url';
const HERE=fileURLToPath(new URL('.',import.meta.url));
const OUT=fileURLToPath(new URL('..',import.meta.url));
const S='/private/tmp/argus-acceptance-20260914';
const require=createRequire(S+'/source/web/package.json');
const {chromium}=require('@playwright/test');
const API='http://localhost:8149/api/v1',WEB='http://localhost:3149';
const captcha=readFileSync(S+'/source/web/lib/guest-captcha.ts','utf8').match(/^export const LOCAL_QA_CAPTCHA_TOKEN = "([^"]+)";/m)[1];
const phase=process.argv[2]||'preflight';
const questions=JSON.parse(readFileSync(S+'/source/docs/reports/evidence/grounded-math/drivers/questions.json','utf8'));
for(const d of ['turns','answers','screenshots'])mkdirSync(OUT+'/'+d,{recursive:true});
const save=(path,data)=>writeFileSync(path,JSON.stringify(data,null,2)+'\n',{mode:0o600});
const browser=await chromium.launch({headless:true});
async function api(context,path,method='GET',data){
 const r=await context.request.fetch(API+path,{method,data,headers:{Origin:WEB}});
 if(!r.ok())throw new Error(`${method} ${path} HTTP ${r.status()} ${(await r.text()).slice(0,250)}`);
 return r.json();
}
async function session(language,guest=false,index=1){
 const context=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:1,isMobile:true,hasTouch:true,locale:language==='en'?'en-US':'es-DO',extraHTTPHeaders:{'x-forwarded-for':`198.51.100.${guest?index+100:language==='en'?81:82}`}});
 let auth;
 if(guest)auth=await api(context,'/auth/guest','POST',{captcha_token:captcha,language});
 else {
  const file=S+'/account-'+language+'.json';
  if(!existsSync(file)){
   const credential={email:`acceptance-${language}-${randomBytes(4).toString('hex')}@example.com`,password:randomBytes(24).toString('hex')};save(file,credential);
   auth=await api(context,'/auth/signup','POST',{...credential,language,display_name:'Acceptance audit',captcha_token:captcha});
  }
  const credential=JSON.parse(readFileSync(file,'utf8'));
  auth=await api(context,'/auth/login','POST',{...credential,captcha_token:captcha});
  await api(context,'/me','PATCH',{language,country:language==='en'?'US':'DO'});
 }
 const me=await api(context,'/me');
 if(guest?me.account_kind!=='guest':me.account_kind!=='registered')throw new Error('persona mismatch '+me.account_kind);
 if(!guest && me.user.country!==(language==='en'?'US':'DO'))throw new Error('country mismatch');
 return {context,me};
}
async function capture(page,id,label){
 const item=page.locator(`[data-message-id="${id}"]`);
 await item.waitFor({timeout:20000});
 await item.evaluate(e=>e.scrollIntoView({block:'start'}));
 await page.waitForTimeout(500);
 await page.mouse.move(1,1);
 await page.screenshot({path:OUT+`/screenshots/${label}.png`});
 return {file:`screenshots/${label}.png`,viewport:{width:390,height:844},rendered_text:await item.innerText()};
}
try{
 if(phase==='rendered'){
  for(const language of ['en','es-419']){const {context}=await session(language);for(const file of readdirSync(OUT+'/turns').filter(f=>f.startsWith('registered-')&&f.endsWith('-'+language+'.json'))){const r=JSON.parse(readFileSync(OUT+'/turns/'+file));const page=await context.newPage();await page.goto(WEB+'/chat?conversation='+r.conversation_id,{waitUntil:'networkidle'});r.screenshot=await capture(page,r.answer.id,r.label);save(OUT+'/turns/'+file,r);await page.close();}await context.close();}
 }else if(phase==='recover'){
  const r=JSON.parse(readFileSync(OUT+'/turns/registered-q1-en.json'));const {context}=await session('en');const page=await context.newPage();await page.goto(WEB+'/chat?conversation='+r.conversation_id,{waitUntil:'networkidle'});await capture(page,r.answer.id,r.label);await context.close();
 }else if(phase==='preflight'){
  const proof=[];
  for(const language of ['en','es-419']){
   const {context,me}=await session(language);const page=await context.newPage();await page.goto(WEB+'/chat',{waitUntil:'networkidle'});
   await page.getByTestId('chat-input').waitFor({timeout:30000});
   proof.push({language,country:me.user.country,currency:me.user.currency,account_kind:me.account_kind,composer:true});
   await page.screenshot({path:OUT+`/screenshots/preflight-${language}.png`});await context.close();
  }
  const {context,me}=await session('en',true,1);proof.push({account_kind:me.account_kind,guest:true});await context.close();
  save(OUT+'/auth-preflight.json',proof);console.log(JSON.stringify(proof));
 }else{
  writeFileSync(S+'/phase.txt',phase);
  const followups=phase==='followups'?JSON.parse(readFileSync(OUT+'/followups.json','utf8')):null;
  for(const language of ['en','es-419']){
   let shared=phase==='guest'?null:await session(language);
   for(const question of questions.filter(q=>phase!=='guest'||['q1','q7','q9'].includes(q.id))){
    if(existsSync(S+'/budget-stop.json'))throw new Error('Budget stop');
    const meter=JSON.parse(execFileSync(S+'/source/.venv/bin/python',[HERE+'meter.py'],{encoding:'utf8'}));
    if(meter.smoke_usd+.65>=9)throw new Error('Budget admission stop');
    const label=`${phase}-${question.id}-${language}`;
    if(existsSync(OUT+'/turns/'+label+'.json'))continue;
    const {context,me}=shared||await session(language,true,(language==='en'?10:20)+Number(question.id.slice(1)));
    let conversation;
    if(phase==='followups')conversation=JSON.parse(readFileSync(OUT+`/turns/registered-${question.id}-${language}.json`)).conversation_id;
    else conversation=(await api(context,'/conversations','POST',{language,title:question[language].slice(0,60)})).conversation.id;
    const message=followups?followups[question.id+'-'+language].message:question[language];
    const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
    await page.goto(WEB+'/chat?conversation='+conversation,{waitUntil:'networkidle'});
    const input=page.getByTestId('chat-input');await input.waitFor({timeout:30000});
    console.log(JSON.stringify({state:'running',label,spent:meter.smoke_usd}));
    const before=(await api(context,`/conversations/${conversation}/messages?limit=100`)).items.map(x=>x.id);
    const responsePromise=page.waitForResponse(r=>r.url().endsWith('/chat/stream')&&r.request().method()==='POST',{timeout:240000});
    const started=Date.now();await input.fill(message);await page.getByTestId('chat-send').click();
    const response=await responsePromise;const posted=response.request().postDataJSON();conversation=posted.conversation_id||conversation;const body=await response.text();
    const frames=body.split('\n').filter(l=>l.startsWith('data:')).map(l=>l.slice(5).trim()).filter(l=>l&&l!=='[DONE]').map(l=>JSON.parse(l));
    let items,answer;
    for(let i=0;i<120;i++){
     items=(await api(context,`/conversations/${conversation}/messages?limit=100`)).items;
     answer=items.filter(x=>x.role==='assistant'&&!before.includes(x.id)).at(-1);
     const jobs=frames.filter(x=>x.type==='final').flatMap(x=>x.payload?.tool_jobs||[]);
     let pending=false;
     for(const entry of jobs){const jobid=entry.job?.id||entry.job?.job_id;if(!jobid)continue;const state=await api(context,'/backtest-jobs/'+jobid);if(state.result_message)answer=state.result_message;else if(['queued','running'].includes(state.job?.status))pending=true;}
     if(answer&&!pending)break;await page.waitForTimeout(1000);
    }
    if(!answer)throw new Error('No stored answer');
    await page.waitForTimeout(900);
    let screenshot;
    try{screenshot=await capture(page,answer.id,label);}catch(e){await page.reload({waitUntil:'networkidle'});screenshot=await capture(page,answer.id,label);}
    const record={label,phase,question:question.id,language,country:me.user.country||null,account_kind:me.account_kind,conversation_id:conversation,message,answer,frames,http_status:response.status(),done:body.includes('[DONE]'),elapsed_seconds:(Date.now()-started)/1000,screenshot,page_errors:errors};
    save(OUT+'/turns/'+label+'.json',record);
    writeFileSync(OUT+'/answers/'+label+'.md',`# ${label}\n\n${message}\n\n${answer.content||screenshot.rendered_text||''}`.trimEnd()+'\n');
    console.log(JSON.stringify({state:'recorded',label,seconds:record.elapsed_seconds}));
    await page.close();if(!shared)await context.close();
   }
   if(shared)await shared.context.close();
  }
 }
}finally{await browser.close();}
