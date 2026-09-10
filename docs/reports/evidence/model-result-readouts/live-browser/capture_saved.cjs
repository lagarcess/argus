/* Final saved-state acceptance. No POSTs and no external browser requests. */
const fs = require('node:fs'), path = require('node:path');
const { chromium } = require(path.join(process.cwd(), 'web/node_modules/playwright'));
const out = __dirname, api = 'http://127.0.0.1:8540', web = 'http://127.0.0.1:3220';
const locales = Object.fromEntries(['en','es-419'].map(lang => [lang, require(path.join(process.cwd(),'web/public/locales',lang,'common.json'))]));
const normalize = value => value.replace(/\s+/g,' ').trim();
const state = async () => (await fetch(`${api}/qa/state`)).json();
const assert = (value, message) => { if (!value) throw new Error(message); };
(async () => {
  const before = await state();
  const browser = await chromium.launch({ headless:true });
  const context = await browser.newContext({ viewport:{width:1440,height:1050}, permissions:['clipboard-read','clipboard-write'] });
  const page = await context.newPage(), events = [], observations = [];
  page.on('console',message=>{if(['warning','error'].includes(message.type()))events.push({type:message.type(),text:message.text()});});
  page.on('pageerror',error=>events.push({type:'pageerror',text:String(error)}));
  await context.route('**/*',route=> {
    const request=route.request();
    return !['127.0.0.1','localhost'].includes(new URL(request.url()).hostname) || request.method()==='POST' ? route.abort() : route.continue();
  });
  let language='en';
  async function changeLanguage(next) {
    language=await page.locator('html').getAttribute('lang');
    if(language===next)return;
    const expand=page.getByRole('button',{name:'Expand sidebar',exact:true});
    if(await expand.isVisible())await expand.click();
    await page.getByRole('button',{name:locales[language].settings.title,exact:true}).click();
    await page.getByRole('button',{name:language==='en'?'Preferences':'Preferencias',exact:true}).click();
    await page.getByRole('button',{name:locales[language].settings.app.language,exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:next==='en'?/^English/:/^Español/}).click();
    language=next;
    await page.waitForFunction(expected=>document.documentElement.lang===expected,language);
    await page.locator('.argus-result-breakdown').waitFor();
  }
  async function capture(label, sourceLanguage, envelope) {
    const q=page.locator('.argus-result-readout').last(), b=page.locator('.argus-result-breakdown').last();
    await b.waitFor();
    const quick=await q.innerText(), breakdown=await b.innerText();
    assert(!`${quick}\n${breakdown}`.includes('—'),`${label}: em dash`);
    assert(await page.getByRole('region',{name:'Hero + Delta Evidence Card',exact:true}).count()===1,`${label}: result card count`);
    const copied=[];
    const more=page.getByRole('button',{name:locales[language].chat.more_actions,exact:true});
    const count=await more.count();
    for(const [index,visible] of [quick,breakdown].entries()) {
      await (index===0?q:b).hover();
      await more.nth(count-2+index).scrollIntoViewIfNeeded();
      await more.nth(count-2+index).click();
      await page.getByRole('menuitem',{name:locales[language].chat.copy_plaintext,exact:true}).press('Enter');
      const text=await page.evaluate(()=>navigator.clipboard.readText());
      assert(index===0?normalize(text).includes(normalize(visible)):normalize(text)===normalize(visible),`${label}: copy mismatch`);
      copied.push(text);
    }
    await b.scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(out,`${label}.png`)});
    await q.screenshot({path:path.join(out,`${label}-quick.png`)});
    await b.screenshot({path:path.join(out,`${label}-breakdown.png`)});
    fs.writeFileSync(path.join(out,`${label}.aria.txt`),await page.locator('body').ariaSnapshot());
    const observation={label,language,source_language:sourceLanguage,quick_take:quick,breakdown,clipboard:copied,clipboard_parity:true,url:page.url(),title:await page.title(),expected_quick_source:sourceLanguage===language&&envelope?.text?'model':'template'};
    observations.push(observation);
    return observation;
  }
  try {
    for(const id of ['docn-en','docn-es','dca-costs','indicator'].filter(id=>fs.existsSync(path.join(out,'stored-runs',`${id}.json`)))) {
      const run=JSON.parse(fs.readFileSync(path.join(out,'stored-runs',`${id}.json`)));
      const envelope=run.conversation_result_card.result_readout_content;
      const sourceLanguage=envelope?.language||'en';
      await page.goto(`${web}/chat?conversation=${run.conversation_id}`);
      await page.locator('.argus-result-breakdown').waitFor();
      language=await page.locator('html').getAttribute('lang');
      await changeLanguage(sourceLanguage);
      const matching=await capture(`final-${id}-match`,sourceLanguage,envelope);
      await page.reload();await page.locator('.argus-result-breakdown').waitFor();
      const reloaded=await capture(`final-${id}-match-reload`,sourceLanguage,envelope);
      assert(normalize(matching.quick_take)===normalize(reloaded.quick_take)&&normalize(matching.breakdown)===normalize(reloaded.breakdown),`${id}: final reload drift`);
      await changeLanguage(sourceLanguage==='en'?'es-419':'en');
      const mismatch=await capture(`final-${id}-mismatch`,sourceLanguage,envelope);
      if(envelope?.text)assert(normalize(matching.quick_take)!==normalize(mismatch.quick_take),`${id}: mismatched Quick take remained visible`);
      await page.reload();await page.locator('.argus-result-breakdown').waitFor();
      const mismatchReload=await capture(`final-${id}-mismatch-reload`,sourceLanguage,envelope);
      assert(normalize(mismatch.quick_take)===normalize(mismatchReload.quick_take)&&normalize(mismatch.breakdown)===normalize(mismatchReload.breakdown),`${id}: mismatch reload drift`);
    }
    await page.setViewportSize({width:390,height:844});
    await page.locator('.argus-result-readout').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(out,'final-mobile.png')});
    await page.locator('.argus-result-readout').screenshot({path:path.join(out,'final-mobile-quick.png')});
    await page.locator('.argus-result-breakdown').screenshot({path:path.join(out,'final-mobile-breakdown.png')});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'mobile horizontal overflow');
    const after=await state();
    assert(before.budget.attempt_count===after.budget.attempt_count,'Saved-state acceptance made a model request');
    fs.writeFileSync(path.join(out,'final-saved-proof.json'),JSON.stringify({candidate_sha:before.candidate_sha,observations,events,before_model_attempts:before.budget.attempt_count,after_model_attempts:after.budget.attempt_count,additional_model_requests:0,mobile_no_horizontal_overflow:true,dca_setup_blocked:!fs.existsSync(path.join(out,'stored-runs/dca-costs.json'))},null,2)+'\n');
    console.log('Final saved matrix passed; zero model requests; clipboard and mobile checked');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
