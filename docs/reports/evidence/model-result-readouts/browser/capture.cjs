/* Local browser transport proof; no new model or backtest quality claims. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const { chromium } = require(path.join(process.cwd(), 'web/node_modules/playwright'));
const root = process.cwd();
const output = __dirname;
const origin = 'http://127.0.0.1:3219';
const api = 'http://127.0.0.1:8539';
const normalize = text => text.replace(/\s+/g, ' ').trim();
const assert = (ok, message) => { if (!ok) throw new Error(message); };
const locales = Object.fromEntries(['en', 'es-419'].map(language => [language, require(path.join(root, 'web/public/locales', language, 'common.json'))]));
const sourceFiles = [
  'web/components/chat/ChatMessage.tsx', 'web/lib/result-readout-display.ts',
  'web/components/chat/ChatInterface.tsx', 'web/components/chat/chat-message-projection.ts',
  'web/components/chat/types.ts', 'web/lib/result-readout-content.ts',
  'web/lib/argus-api.ts', 'web/lib/artifact-response-transport.ts',
  'web/lib/chat-backtest-jobs.ts', 'web/lib/chat-final-message.ts',
  'web/lib/chat-message-hydration.ts', 'web/lib/result-card-view-model.ts',
  'web/lib/chat-message-copy-text.ts', 'web/lib/chat-card-copy-text.ts',
  'web/public/locales/en/common.json', 'web/public/locales/es-419/common.json',
  'src/argus/api/artifact_presentation.py', 'src/argus/domain/result_readout_content.py',
];
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

(async () => {
  // Reset only the local mock user's preference so reruns have the same start.
  // Every language change being accepted is still exercised through Settings.
  const reset = await fetch(`${api}/api/v1/me`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ language: 'en' }) });
  assert(reset.ok, 'Local mock profile reset failed');
  const seed = await (await fetch(`${api}/replay-proof`)).json();
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1050 }, permissions: ['clipboard-read', 'clipboard-write'], locale: 'en-US' });
  const consoleEntries = [], externalBlocked = [], requests = [], failures = [];
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (!['127.0.0.1', 'localhost'].includes(url.hostname)) {
      externalBlocked.push({ method: route.request().method(), host: url.hostname });
      return route.abort('blockedbyclient');
    }
    return route.continue();
  });
  const page = await context.newPage();
  page.on('console', message => { if (['error', 'warning'].includes(message.type())) consoleEntries.push({ type: message.type(), text: message.text() }); });
  page.on('pageerror', error => failures.push(String(error)));
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.port === '8539') requests.push({ method: request.method(), path: url.pathname });
  });
  let language = 'en';
  const frames = () => ({
    quick: page.getByRole('region', { name: locales[language].chat.result_readout.quick_take, exact: true }),
    breakdown: page.getByRole('region', { name: locales[language].chat.result_breakdown.aria_label, exact: true }),
  });
  const load = async caseName => {
    await page.goto(`${origin}/chat?conversation=${seed.cases[caseName]}`);
    await frames().quick.waitFor();
    await frames().breakdown.waitFor();
    assert((await page.title()).includes('Readout replay:'), 'Incorrect page identity');
  };
  const changeLanguage = async next => {
    // This existing sidebar control currently has the same English aria label
    // in both locales; readout-frame labels themselves are localized.
    const expand = page.getByRole('button', { name: 'Expand sidebar', exact: true });
    if (await expand.isVisible()) await expand.click();
    await page.getByRole('button', { name: language === 'en' ? 'Settings' : 'Ajustes', exact: true }).click();
    await page.getByRole('button', { name: language === 'en' ? 'Preferences' : 'Preferencias', exact: true }).click();
    await page.getByRole('button', { name: locales[language].settings.app.language, exact: true }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('button', { name: next === 'en' ? /^English/ : /^Español/ }).click();
    language = next;
    await frames().quick.waitFor();
    await frames().breakdown.waitFor();
    await page.waitForFunction(expected => document.documentElement.lang === expected, language);
  };
  const cases = [];
  const capture = async (name, expectedLanguage, mode, screenshot = true) => {
    const f = frames();
    const quick = await f.quick.locator('.argus-result-readout').innerText();
    const breakdown = await f.breakdown.locator('.argus-result-breakdown').innerText();
    if (mode === 'model') {
      assert(normalize(quick) === normalize(seed.texts[expectedLanguage].quick_take), `${name}: incorrect Quick take model text`);
      assert(normalize(breakdown) === normalize(seed.texts[expectedLanguage].breakdown), `${name}: incorrect Breakdown model text`);
    } else {
      for (const text of Object.values(seed.texts)) {
        assert(!quick.includes(text.quick_take), `${name}: mismatched model Quick take leaked`);
        assert(!breakdown.includes(text.breakdown), `${name}: mismatched model Breakdown leaked`);
      }
    }
    assert(!`${quick}\n${breakdown}`.includes('SYNTHETIC PRIVATE'), `${name}: private content leaked`);
    assert(!`${quick}\n${breakdown}`.includes('—'), `${name}: em dash in readout`);
    assert(await page.getByRole('region', { name: 'Hero + Delta Evidence Card' }).count() === 1, `${name}: result card duplicated or missing`);
    assert(await page.locator('nextjs-portal').evaluateAll(nodes => !nodes.some(node => /Build Error|Runtime Error|Unhandled Runtime/.test(node.innerText))), `${name}: framework overlay`);
    const clipboard = [];
    for (const [index, visible] of [quick, breakdown].entries()) {
      const more = page.getByRole('button', { name: locales[language].chat.more_actions, exact: true }).nth(index);
      await (index === 0 ? f.quick : f.breakdown).hover();
      await more.scrollIntoViewIfNeeded();
      await more.click();
      // Keyboard activation also exercises the real clipboard handler when a
      // following message overlaps the historical message's menu hit target.
      await page.getByRole('menuitem', { name: locales[language].chat.copy_plaintext, exact: true }).press('Enter');
      const copied = await page.evaluate(() => navigator.clipboard.readText());
      assert(index === 0 ? normalize(copied).includes(normalize(visible)) : normalize(copied) === normalize(visible), `${name}: ${index === 0 ? 'Quick take' : 'Breakdown'} clipboard mismatch`);
      clipboard.push(copied);
    }
    await f.breakdown.scrollIntoViewIfNeeded();
    if (screenshot) await page.screenshot({ path: path.join(output, `${name}.png`), fullPage: false });
    fs.writeFileSync(path.join(output, `${name}.aria.txt`), await page.locator('body').ariaSnapshot());
    cases.push({ name, mode, language, quick_take: quick, breakdown, clipboard_parity: true, url: page.url(), title: await page.title(), screenshot: screenshot ? `${name}.png` : null });
  };
  try {
    await load('new-en');
    await capture('new-en-match', 'en', 'model');
    await page.getByRole('region', { name: 'Hero + Delta Evidence Card' }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, 'new-en-result-card.png') });
    await changeLanguage('es-419');
    await capture('new-en-mismatch-es', 'es-419', 'template');
    await page.reload(); await frames().breakdown.waitFor();
    await capture('new-en-mismatch-es-reload', 'es-419', 'template', false);
    await load('new-es');
    await capture('new-es-match', 'es-419', 'model');
    await changeLanguage('en');
    await capture('new-es-mismatch-en', 'en', 'template');
    await page.reload(); await frames().breakdown.waitFor();
    await capture('new-es-mismatch-en-reload', 'en', 'template', false);
    await load('legacy');
    await capture('legacy-en', 'en', 'template');
    await changeLanguage('es-419');
    await capture('legacy-es', 'es-419', 'template');
    await page.reload(); await frames().breakdown.waitFor();
    await capture('legacy-es-reload', 'es-419', 'template', false);
    for (const lang of ['en', 'es-419']) {
      const templates = cases.filter(item => item.mode === 'template' && item.language === lang);
      assert(templates.every(item => item.quick_take === templates[0].quick_take && item.breakdown === templates[0].breakdown), `${lang}: mismatch and legacy template diverged`);
    }
    await load('new-es');
    await page.setViewportSize({ width: 390, height: 844 });
    const f = frames();
    await f.quick.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, 'new-es-mobile-quick-take.png') });
    await f.breakdown.scrollIntoViewIfNeeded();
    await f.breakdown.locator('p').last().scrollIntoViewIfNeeded();
    await f.breakdown.hover();
    await page.mouse.wheel(0, 600);
    await page.waitForFunction(() => {
      const paragraphs = document.querySelectorAll('.argus-result-breakdown p');
      const last = paragraphs[paragraphs.length - 1];
      return last && last.getBoundingClientRect().bottom < window.innerHeight - 140;
    });
    await page.screenshot({ path: path.join(output, 'new-es-mobile-breakdown.png') });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'Mobile horizontal overflow');
    const finalProof = await (await fetch(`${api}/replay-proof`)).json();
    delete finalProof.texts;
    const runtimeDirty = execFileSync('git', ['status', '--porcelain', '--', ...sourceFiles], { encoding: 'utf8' }).trim();
    const report = {
      status: 'passed', captured_at: new Date().toISOString(),
      candidate_sha: execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(),
      runtime_worktree_clean: !runtimeDirty,
      evidence_kind: `${runtimeDirty ? 'working-tree' : 'committed-runtime'} provider-free transport replay; synthetic new readouts and Breakdown rows, genuine pre-lane META result/card`,
      browser: 'Chromium via repository Playwright; Browser plugin not available',
      desktop_viewport: { width: 1440, height: 1050 }, mobile_viewport: { width: 390, height: 844 },
      source_hashes: Object.fromEntries(sourceFiles.filter(file => fs.existsSync(file)).map(file => [file, sha256(file)])),
      cases, console_entries: consoleEntries, page_errors: failures, external_requests_blocked: externalBlocked,
      api_requests: requests, api_proof: finalProof,
      checks: { language_match: true, language_mismatch: true, legacy_templates: true, settings_switch: true, reload: true, clipboard_parity: true, mobile_no_horizontal_overflow: true, result_card_preserved: true },
    };
    assert(failures.length === 0, 'Browser page errors');
    assert(consoleEntries.filter(entry => entry.type === 'error').length === 0, 'Browser console errors');
    assert(externalBlocked.length === 0, 'Unexpected external browser request');
    assert(finalProof.blocked_network.length === 0, 'Unexpected backend network attempt');
    assert(finalProof.blocked_generation_requests.length === 0, 'Unexpected generation request');
    assert(finalProof.stored_messages_unchanged, 'A read or language switch rewrote the fixture messages');
    for (const [file, loadedHash] of Object.entries(finalProof.loaded_reader_source_hashes)) {
      assert(report.source_hashes[file] === loadedHash, `Replay API loaded stale source: ${file}`);
    }
    assert(!requests.some(request => request.method === 'POST' && /chat|backtest/.test(request.path)), 'Generation call from browser');
    fs.writeFileSync(path.join(output, 'proof.json'), JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify({ status: report.status, cases: cases.length, api_requests: requests.length, console_warnings: consoleEntries.length, output }, null, 2));
  } catch (error) {
    fs.writeFileSync('/tmp/readout-replay-failure.json', JSON.stringify({ error: String(error), consoleEntries, failures, cases }, null, 2));
    fs.writeFileSync('/tmp/readout-replay-failure.aria.txt', await page.locator('body').ariaSnapshot());
    await page.screenshot({ path: '/tmp/readout-replay-failure.png' });
    throw error;
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
