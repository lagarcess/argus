/* Four authorized fresh runs, no outer retries. Each action checks the $1 ledger. */
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(path.join(process.cwd(), 'web/node_modules/playwright'));
const output = __dirname;
const web = 'http://127.0.0.1:3220';
const api = 'http://127.0.0.1:8540';
const locales = Object.fromEntries(['en', 'es-419'].map(lang => [lang, require(path.join(process.cwd(), 'web/public/locales', lang, 'common.json'))]));
const cases = [
  { id: 'docn-en', language: 'en', prompt: 'Buy and hold DOCN from September 1, 2023 through September 9, 2026 with $1,000 starting capital, against SPY. No fees or slippage.' },
  { id: 'docn-es', language: 'es-419', prompt: 'Compra y mantén DOCN del 1 de septiembre de 2023 al 9 de septiembre de 2026, con capital inicial de $1,000. Compáralo con SPY, sin comisiones ni deslizamiento.' },
  { id: 'dca-costs', language: 'en', prompt: 'Test monthly dollar-cost averaging in DOCN from September 10, 2025 through September 9, 2026. Start with $1,000 and contribute $100 every month. Compare with SPY. Model a 10 basis point fee and 5 basis points slippage per trade.' },
  { id: 'indicator', language: 'en', prompt: 'Test an RSI strategy in SPY from September 10, 2025 through September 9, 2026 with $1,000 starting capital. Buy when 14-day RSI drops below 30 and sell when it rises above 70. Compare with SPY. No fees or slippage.' },
];
const assert = (value, message) => { if (!value) throw new Error(message); };
const state = async () => {
  const response = await fetch(`${api}/qa/state`);
  const snapshot = await response.json();
  assert(!snapshot.budget.halted, `Budget halt: ${snapshot.budget.halted}`);
  assert(snapshot.runtime_source_clean, 'Runtime source changed during browser proof');
  return snapshot;
};

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1050 }, locale: 'en-US', permissions: ['clipboard-read', 'clipboard-write'] });
  const page = await context.newPage();
  const events = [], results = [];
  page.on('console', message => { if (['warning', 'error'].includes(message.type())) events.push({ type: message.type(), text: message.text() }); });
  page.on('pageerror', error => events.push({ type: 'pageerror', text: String(error) }));
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (!['127.0.0.1', 'localhost'].includes(url.hostname)) {
      events.push({ type: 'external_request_blocked', host: url.hostname });
      return route.abort();
    }
    return route.continue();
  });
  let language = 'en';
  const quick = () => page.getByRole('region', { name: locales[language].chat.result_readout.quick_take, exact: true }).last();
  const breakdown = () => page.getByRole('region', { name: locales[language].chat.result_breakdown.aria_label, exact: true }).last();
  async function changeLanguage(next) {
    if (next === language) return;
    const expand = page.getByRole('button', { name: 'Expand sidebar', exact: true });
    if (await expand.isVisible()) await expand.click();
    await page.getByRole('button', { name: locales[language].settings.title, exact: true }).click();
    await page.getByRole('button', { name: language === 'en' ? 'Preferences' : 'Preferencias', exact: true }).click();
    await page.getByRole('button', { name: locales[language].settings.app.language, exact: true }).click();
    await page.getByRole('dialog').getByRole('button', { name: next === 'en' ? /^English/ : /^Español/ }).click();
    language = next;
    await page.waitForFunction(expected => document.documentElement.lang === expected, language);
  }
  async function save(name, includeBreakdown = true) {
    const q = await quick().innerText();
    const b = includeBreakdown ? await breakdown().innerText() : null;
    await (includeBreakdown ? breakdown() : quick()).scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, `${name}.png`) });
    fs.writeFileSync(path.join(output, `${name}.aria.txt`), await page.locator('body').ariaSnapshot());
    return { language, quick_take: q, breakdown: b, url: page.url(), title: await page.title() };
  }
  try {
    const initial = await state();
    assert(initial.run_attempts.length === 0 && initial.budget.attempt_count === 0, 'No paid replay or reset allowed');
    await page.goto(`${web}/chat`);
    await page.getByRole('combobox').waitFor();
    for (const item of cases) {
      await state();
      await fetch(`${api}/qa/case`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ case: item.id }) });
      await changeLanguage(item.language);
      await page.goto(`${web}/chat`);
      await page.getByRole('combobox').waitFor();
      await page.getByRole('combobox').fill(item.prompt);
      await page.getByRole('button', { name: language === 'en' ? 'Send message' : 'Enviar mensaje', exact: true }).click();
      console.log(`Submitted one setup turn: ${item.id}`);
      const runButton = page.getByRole('button', { name: locales[language].chat.confirmation.actions.run_backtest, exact: true });
      await runButton.waitFor({ timeout: 90000 });
      const beforeRun = await state();
      fs.writeFileSync(path.join(output, `${item.id}-confirmation.aria.txt`), await page.locator('body').ariaSnapshot());
      await runButton.click();
      await quick().waitFor({ timeout: 90000 });
      const afterRun = await state();
      assert(afterRun.run_attempts.length === beforeRun.run_attempts.length + 1, 'Unexpected real backtest attempt count');
      const first = await save(`${item.id}-quick-take`, false);
      await page.getByRole('button', { name: locales[language].chat.result_card.explain_result, exact: true }).click();
      await breakdown().waitFor({ timeout: 90000 });
      await state();
      const matching = await save(`${item.id}-match`);
      await page.reload(); await breakdown().waitFor();
      const reloaded = await save(`${item.id}-match-reload`);
      assert(matching.quick_take === reloaded.quick_take && matching.breakdown === reloaded.breakdown, 'Reload changed stored frame text');
      const opposite = language === 'en' ? 'es-419' : 'en';
      const beforeSwitch = await state();
      await changeLanguage(opposite);
      const mismatch = await save(`${item.id}-mismatch`);
      await page.reload(); await breakdown().waitFor();
      const mismatchReload = await save(`${item.id}-mismatch-reload`);
      assert(mismatch.quick_take === mismatchReload.quick_take && mismatch.breakdown === mismatchReload.breakdown, 'Mismatch reload changed templates');
      const afterSwitch = await state();
      assert(beforeSwitch.budget.attempt_count === afterSwitch.budget.attempt_count, 'Language read made a model call');
      results.push({ ...item, first, matching, reloaded, mismatch, mismatchReload, budget: afterSwitch.budget });
      fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify({ results, events }, null, 2) + '\n');
      console.log(JSON.stringify({ completed: item.id, attempts: afterSwitch.budget.attempt_count, spent_usd: afterSwitch.budget.reported_cost_usd, runs: afterSwitch.run_attempts.length }));
    }
    const final = await state();
    fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify({ status: 'core_four_completed', results, events, environment: final }, null, 2) + '\n');
  } catch (error) {
    const snapshot = await (await fetch(`${api}/qa/state`)).json();
    await page.screenshot({ path: path.join(output, 'stopped.png') });
    fs.writeFileSync(path.join(output, 'stopped.aria.txt'), await page.locator('body').ariaSnapshot());
    fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify({ status: 'stopped', error: String(error), results, events, environment: snapshot }, null, 2) + '\n');
    console.error(error);
    process.exitCode = 1;
  } finally { await browser.close(); }
})();
