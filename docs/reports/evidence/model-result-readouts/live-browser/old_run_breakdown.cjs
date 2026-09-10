/* One newly requested Breakdown on a genuine old run; no additional backtest. */
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(path.join(process.cwd(), 'web/node_modules/playwright'));
const out = __dirname, api = 'http://127.0.0.1:8540', web = 'http://127.0.0.1:3220';
const state = async () => (await fetch(`${api}/qa/state`)).json();
(async () => {
  const before = await state();
  if (before.budget.halted || before.run_attempts.length !== 3 || !before.run_attempts.some(row=>row.case==='indicator')) throw new Error('Completed RSI and both DOCN cases plus available budget required');
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } });
  const events = [];
  page.on('console', message => { if (['warning', 'error'].includes(message.type())) events.push({ type: message.type(), text: message.text() }); });
  page.on('pageerror', error => events.push({ type: 'pageerror', text: String(error) }));
  await page.route('**/*', route => ['127.0.0.1', 'localhost'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
  try {
    await fetch(`${api}/qa/case`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ case: 'old-run-new-breakdown' }) });
    await page.goto(`${web}/chat?conversation=${before.old_conversation_id}`);
    await page.getByRole('combobox').waitFor();
    let language = await page.locator('html').getAttribute('lang');
    if (language === 'en') {
      const expand = page.getByRole('button', { name: 'Expand sidebar', exact: true });
      if (await expand.isVisible()) await expand.click();
      await page.getByRole('button', { name: 'Settings', exact: true }).click();
      await page.getByRole('button', { name: 'Preferences', exact: true }).click();
      await page.getByRole('button', { name: 'App language', exact: true }).click();
      await page.getByRole('dialog').getByRole('button', { name: /^Español/ }).click();
      language = 'es-419';
      await page.waitForFunction(expected => document.documentElement.lang === expected, language);
    }
    const label = language === 'en' ? 'Explain result' : 'Explicar resultado';
    fs.writeFileSync(path.join(out, 'old-run-before-new-breakdown.aria.txt'), await page.locator('body').ariaSnapshot());
    await page.screenshot({ path: path.join(out, 'old-run-before-new-breakdown.png') });
    const run = JSON.parse(fs.readFileSync(path.join(out, 'stored-runs/old-run-new-breakdown.json')));
    const response = await fetch(`${api}/api/v1/chat/stream`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ conversation_id: before.old_conversation_id, language, action: { type: 'show_breakdown', label, labelKey: 'chat.result_card.explain_result', presentation: 'result', payload: { run_id: run.id, conversation_id: before.old_conversation_id } } }) });
    if (!response.ok) throw new Error(`Old-run typed action HTTP${response.status}`);
    const stream = await response.text();
    fs.writeFileSync(path.join(out, 'old-run-new-breakdown-stream.txt'), stream);
    await page.reload();
    await page.getByRole('region', { name: language === 'en' ? 'Result breakdown' : 'Desglose del resultado', exact: true }).waitFor({ timeout: 90000 });
    await page.waitForFunction(() => document.querySelector('[role=combobox]')?.getAttribute('aria-disabled') !== 'true', null, { timeout: 90000 });
    const capture = async (name) => {
      const breakdown = page.locator('.argus-result-breakdown').last();
      await breakdown.scrollIntoViewIfNeeded();
      await page.screenshot({ path: path.join(out, `${name}.png`) });
      fs.writeFileSync(path.join(out, `${name}.aria.txt`), await page.locator('body').ariaSnapshot());
      return { language, quick_take: await page.locator('.argus-result-readout').allInnerTexts(), breakdown: await breakdown.innerText(), url: page.url() };
    };
    const matching = await capture('old-run-new-breakdown');
    const afterModel = await state();
    await page.reload();
    await page.locator('.argus-result-breakdown').waitFor();
    const reloaded = await capture('old-run-new-breakdown-reload');
    const afterRead = await state();
    if (afterRead.run_attempts.length !== before.run_attempts.length || afterModel.budget.attempt_count !== afterRead.budget.attempt_count) throw new Error('Unexpected backtest or model request on reload');
    const messages = JSON.parse(fs.readFileSync(path.join(out, 'messages.json')))[before.old_conversation_id];
    const readout = messages.filter(message => message.metadata?.result_readout_content?.surface === 'breakdown').at(-1);
    fs.writeFileSync(path.join(out, 'old-run-breakdown-proof.json'), JSON.stringify({ candidate_sha: before.candidate_sha, trigger: 'canonical typed API show_breakdown action because sparse old card has no rendered button', matching, reloaded, new_breakdown_envelope: readout?.metadata.result_readout_content, metadata: readout?.metadata, events, before_model_attempts: before.budget.attempt_count, after_model_attempts: afterModel.budget.attempt_count, additional_backtests: afterRead.run_attempts.length - before.run_attempts.length, reload_model_requests: afterRead.budget.attempt_count - afterModel.budget.attempt_count }, null, 2) + '\n');
    console.log(JSON.stringify({ old_run_new_breakdown: true, language, source: readout?.metadata.result_readout_source, model_attempts: afterModel.budget.attempt_count - before.budget.attempt_count, accounted_cost: afterRead.budget.accounted_cost_usd }));
  } catch (error) {
    fs.writeFileSync(path.join(out, 'old-run-breakdown-stopped.json'), JSON.stringify({ error: String(error), state: await state(), events }, null, 2));
    await page.screenshot({ path: path.join(out, 'old-run-breakdown-stopped.png') });
    throw error;
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
