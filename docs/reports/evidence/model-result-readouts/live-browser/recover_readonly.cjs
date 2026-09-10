/* Inspect the saved first attempt after the dollar guard halted. No POST/chat. */
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(path.join(process.cwd(), 'web/node_modules/playwright'));
const out = __dirname;
const api = 'http://127.0.0.1:8540';
const run = require(path.join(out, 'stored-runs/docn-en.json'));
const url = `http://127.0.0.1:3220/chat?conversation=${run.conversation_id}`;
const state = async () => (await fetch(`${api}/qa/state`)).json();
(async () => {
  const before = await state();
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } });
  const consoleEntries = [];
  page.on('console', message => { if (['error', 'warning'].includes(message.type())) consoleEntries.push({ type: message.type(), text: message.text() }); });
  await page.route('**/*', route => {
    const request = route.request();
    const parsed = new URL(request.url());
    if (!['127.0.0.1', 'localhost'].includes(parsed.hostname) || request.method() === 'POST') return route.abort();
    return route.continue();
  });
  const observations = [];
  async function capture(label, language) {
    await page.getByRole('region', { name: language === 'en' ? 'Result breakdown' : 'Desglose del resultado', exact: true }).waitFor();
    const body = await page.locator('body').ariaSnapshot();
    const frame = page.getByRole('region', { name: language === 'en' ? 'Result breakdown' : 'Desglose del resultado', exact: true });
    await frame.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(out, `${label}.png`) });
    fs.writeFileSync(path.join(out, `${label}.aria.txt`), body);
    observations.push({ label, language, url: page.url(), title: await page.title(), quick_take: await page.locator('.argus-result-readout').innerText(), breakdown: await page.locator('.argus-result-breakdown').innerText() });
  }
  await page.goto(url);
  await capture('docn-en-saved-match', 'en');
  await page.reload(); await capture('docn-en-saved-match-reload', 'en');
  const expand = page.getByRole('button', { name: 'Expand sidebar', exact: true });
  if (await expand.isVisible()) await expand.click();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'Preferences', exact: true }).click();
  await page.getByRole('button', { name: 'App language', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: /^Español/ }).click();
  await capture('docn-en-saved-mismatch-es', 'es-419');
  await page.reload(); await capture('docn-en-saved-mismatch-es-reload', 'es-419');
  const after = await state();
  if (after.budget.attempt_count !== before.budget.attempt_count) throw new Error('Read-only recovery triggered a model request');
  fs.writeFileSync(path.join(out, 'readonly-recovery.json'), JSON.stringify({ candidate_sha: before.candidate_sha, observations, console_entries: consoleEntries, before_attempt_count: before.budget.attempt_count, after_attempt_count: after.budget.attempt_count, additional_model_requests: 0, scope: 'Saved first-attempt result only; accepted Qwen Quick take and template Breakdown after budget halt' }, null, 2) + '\n');
  await browser.close();
  console.log('Saved four read-only frame states; zero additional model requests');
})().catch(error => { console.error(error); process.exitCode = 1; });
