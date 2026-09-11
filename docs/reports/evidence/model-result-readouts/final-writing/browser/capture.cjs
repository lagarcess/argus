/* Offline evidence sheets contain real Argus frame screenshots, never replacement UI. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');
const { chromium } = require(path.join(process.cwd(), 'web/node_modules/playwright'));
const args = process.argv.slice(2);
const flag = (key, fallback) => args.includes(key) ? args[args.indexOf(key) + 1] : fallback;
const output = path.resolve(flag('--output', __dirname));
const origin = `http://127.0.0.1:${flag('--web-port', '3221')}`;
const api = `http://127.0.0.1:${flag('--api-port', '8541')}`;
const normalize = text => text.replace(/\s+/g, ' ').trim();
const assert = (value, message) => { if (!value) throw new Error(message); };
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const escape = value => String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const locales = Object.fromEntries(['en', 'es-419'].map(lang => [lang, require(path.join(process.cwd(), 'web/public/locales', lang, 'common.json'))]));

(async () => {
  const React = require(path.join(process.cwd(), 'web/node_modules/react'));
  const { renderToStaticMarkup } = require(path.join(process.cwd(), 'web/node_modules/react-dom/server'));
  const { default: ReactMarkdown } = await import(pathToFileURL(require.resolve(path.join(process.cwd(), 'web/node_modules/react-markdown'))));
  const { default: remarkGfm } = await import(pathToFileURL(require.resolve(path.join(process.cwd(), 'web/node_modules/remark-gfm'))));
  const markdownHtml = text => renderToStaticMarkup(React.createElement(ReactMarkdown, { remarkPlugins: [remarkGfm] }, text));
  fs.mkdirSync(output, { recursive: true });
  const seed = await (await fetch(`${api}/replay-proof`)).json();
  assert(seed.synthetic_browser_preflight === args.includes('--synthetic-preflight'), 'Synthetic mode must be explicit');
  assert(seed.reader_sha === execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(), 'Reader SHA changed');
  const webSource = JSON.parse(fs.readFileSync(path.join(output, 'web-source.json')));
  assert(webSource.reader_sha === seed.reader_sha, 'Web/API source mismatch');
  for (const [file, expected] of Object.entries({ ...webSource.tracked_source_sha256, ...seed.loaded_reader_hashes })) {
    assert(hash(file) === expected, `Source changed: ${file}`);
  }
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, permissions: ['clipboard-read', 'clipboard-write'] });
  const blocked = [], errors = [], consoleEntries = [], requests = [], outcomes = [];
  await context.route('**/*', route => {
    const request = route.request();
    const url = new URL(request.url());
    if (!['127.0.0.1', 'localhost'].includes(url.hostname) ||
        (!['GET', 'HEAD', 'OPTIONS'].includes(request.method()) && !(request.method() === 'PATCH' && url.pathname === '/api/v1/me'))) {
      blocked.push({ method: request.method(), host: url.hostname, path: url.pathname });
      return route.abort('blockedbyclient');
    }
    return route.continue();
  });
  const page = await context.newPage();
  page.on('console', event => { if (['error', 'warning'].includes(event.type())) consoleEntries.push({ type: event.type(), text: event.text() }); });
  page.on('pageerror', error => errors.push(String(error)));
  page.on('request', request => { const url = new URL(request.url()); if (url.origin === api) requests.push({ method: request.method(), path: url.pathname }); });
  let language = 'en';
  const frame = surface => page.getByRole('region', {
    name: surface === 'quick_take' ? locales[language].chat.result_readout.quick_take : locales[language].chat.result_breakdown.aria_label, exact: true,
  });
  const body = surface => frame(surface).locator(surface === 'quick_take' ? '.argus-result-readout' : '.argus-result-breakdown');
  const setLanguage = async next => {
    if (language === next) return;
    const expand = page.getByRole('button', { name: 'Expand sidebar', exact: true });
    if (await expand.isVisible()) await expand.click();
    await page.getByRole('button', { name: language === 'en' ? 'Settings' : 'Ajustes', exact: true }).click();
    await page.getByRole('button', { name: language === 'en' ? 'Preferences' : 'Preferencias', exact: true }).click();
    await page.getByRole('button', { name: locales[language].settings.app.language, exact: true }).click();
    await page.getByRole('dialog').getByRole('button', { name: next === 'en' ? /^English/ : /^Español/ }).click();
    language = next;
    await page.waitForFunction(lang => document.documentElement.lang === lang, language);
  };
  try {
    const reset = await fetch(`${api}/api/v1/me`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ language: 'en' }) });
    assert(reset.ok, 'Mock profile reset failed');
    for (const pair of seed.cases) {
      await page.goto(`${origin}/chat?conversation=${pair.conversation_id}`);
      await frame('breakdown').waitFor();
      await setLanguage(pair.language);
      await frame('breakdown').waitFor();
      assert((await page.title()).includes('Writing replay:'), 'Wrong page identity');
      assert(await page.getByRole('region', { name: 'Hero + Delta Evidence Card' }).count() === 1, 'Missing/duplicate result card');
      assert(await page.locator('nextjs-portal').evaluateAll(nodes => !nodes.some(node => /Build Error|Runtime Error|Unhandled Runtime/.test(node.innerText))), 'Framework overlay');
      const before = {};
      for (const [index, surface] of ['quick_take', 'breakdown'].entries()) {
        const outcome = pair.outcomes[surface];
        const visible = await body(surface).innerText();
        const renderedLinks = await body(surface).locator('a').evaluateAll(nodes => nodes.map(node => ({ text: node.textContent, href: node.getAttribute('href') })));
        before[surface] = visible;
        assert(visible.trim(), 'Empty frame');
        if (outcome.accepted) {
          const expected = await page.evaluate(html => new DOMParser().parseFromString(html, 'text/html').body.textContent, markdownHtml(outcome.accepted_text));
          assert(normalize(await body(surface).textContent()) === normalize(expected), `${pair.key}/${surface}: accepted text differs`);
          const expectedLinks = await page.evaluate(html => Array.from(new DOMParser().parseFromString(html, 'text/html').body.querySelectorAll('a')).map(node => ({ text: node.textContent, href: node.getAttribute('href') })), markdownHtml(outcome.accepted_text));
          assert(JSON.stringify(renderedLinks) === JSON.stringify(expectedLinks), 'Accepted citation labels or links changed');
        }
        else for (const draft of outcome.raw_drafts.filter(item => typeof item === 'string' && item.trim())) {
          assert(!visible.includes(draft), 'Rejected raw draft appeared as accepted text');
        }
        for (const rejectedText of outcome.rejected_texts) {
          const rejectedVisible = await page.evaluate(html => new DOMParser().parseFromString(html, 'text/html').body.textContent, markdownHtml(rejectedText));
          assert(!normalize(await body(surface).textContent()).includes(normalize(rejectedVisible)), 'Rejected text from raw JSON appeared in product frame');
        }
        assert(!visible.includes('—'), 'Em dash in product frame');
        await frame(surface).hover();
        const more = page.getByRole('button', { name: locales[language].chat.more_actions, exact: true }).nth(index);
        await more.scrollIntoViewIfNeeded();
        await more.click();
        await page.getByRole('menuitem', { name: locales[language].chat.copy_plaintext, exact: true }).press('Enter');
        const copied = await page.evaluate(() => navigator.clipboard.readText());
        if (outcome.accepted) assert(index === 0 ? normalize(copied).includes(normalize(outcome.accepted_text)) : normalize(copied) === normalize(outcome.accepted_text), 'Accepted clipboard mismatch');
        else assert(index === 0 ? normalize(copied).includes(normalize(visible)) : normalize(copied) === normalize(visible), 'Fallback clipboard mismatch');
        const name = `${pair.key}-${surface}`;
        const framePath = path.join(output, `${name}-frame.png`);
        await frame(surface).screenshot({ path: framePath });
        fs.writeFileSync(path.join(output, `${name}.aria.txt`), await frame(surface).ariaSnapshot());
        const provenance = {
          case_id: pair.case_id, locale: language, surface,
          accepted: outcome.accepted, fallback_used: !outcome.accepted,
          failure_mode: outcome.failure_mode || null,
          readout_source: outcome.source || null,
          model_provider: outcome.provider,
          reader_sha: seed.reader_sha, measurement_checkouts: seed.measurement_checkouts,
          report_sha256: seed.report_sha256, source: pair.source,
          requests: outcome.requests, provider_responses: outcome.provider_responses,
          blocked_dispatches: outcome.blocked_dispatches,
          web_sources: outcome.sources || [],
          outcome_usage: outcome.usage || null,
          rendered_links: renderedLinks,
          stored_transport: pair.transport[surface],
          complete_server_outcome: outcome.complete_text || null,
          visible_text: visible, clipboard_text: copied,
          synthetic_browser_preflight: seed.synthetic_browser_preflight,
        };
        fs.writeFileSync(path.join(output, `${name}.json`), JSON.stringify(provenance, null, 2) + '\n');
        const rejected = !outcome.accepted;
        const raw = outcome.raw_drafts.length ? outcome.raw_drafts.map(draft => `<pre>${escape(typeof draft === 'string' ? draft : JSON.stringify(draft))}</pre>`).join('') : '<p>No complete raw draft was returned.</p>';
        const webSources = (outcome.sources || []).length ? `<div class="diagnostic"><h2>WEB SOURCE PROVENANCE</h2><p>External context only. These records do not alter or supply the backtest figures in the canonical source table.</p><pre>${escape(JSON.stringify(outcome.sources, null, 2))}</pre></div>` : '';
        const html = `<!doctype html><html lang="${language}"><meta charset="utf-8"><title>${escape(name)}</title><style>
          *{box-sizing:border-box}body{margin:0;padding:32px;background:#f1f3f6;color:#18202c;font:17px/1.45 system-ui}h1{font-size:28px;margin:0 0 10px}h2{font-size:20px}header,section{background:white;border:1px solid #ccd3df;border-radius:12px;padding:22px}header{margin-bottom:20px}main{display:grid;grid-template-columns:1.25fr 1fr;gap:20px;align-items:start}img{display:block;width:100%;height:auto;border:1px solid #ccd3df}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.4 ui-monospace;margin:0}table{border-collapse:collapse;width:100%;font:13px/1.35 ui-monospace}td{padding:5px;border-bottom:1px solid #e6e9ee;overflow-wrap:anywhere}td:first-child{width:72%}.diagnostic{margin-top:22px;border:2px solid #c78621;padding:18px}.note{font-size:14px;color:#45526a}.stamp{font-weight:700;color:${rejected ? '#944b00' : '#176b42'}}
          </style><header><h1>${escape(pair.case_id)} · ${escape(language)} · ${escape(surface)}</h1><div class="stamp">${seed.synthetic_browser_preflight ? 'SYNTHETIC HARNESS PREFLIGHT · ' : ''}${rejected ? 'REJECTED / UNAVAILABLE: COMPLETE PRODUCT FALLBACK' : 'ACCEPTED MODEL TEXT'}</div><p class="note">Provider-free browser replay of existing measurement. No new model call or backtest. Frame below is a screenshot of the actual Argus UI. Diagnostic/source panels are evidence, not product UI.</p><pre>Reader: ${escape(seed.reader_sha)}\nMeasurement: ${escape(JSON.stringify(seed.measurement_checkouts))}\nSource: ${escape(pair.source_path)}\nSource SHA256: ${escape(pair.source.sha256)}\nFrame provider: ${escape(outcome.provider)}\nFailure: ${escape(outcome.failure_mode || 'none')}</pre></header><main><section><h2>${escape(surface === 'quick_take' ? locales[language].chat.result_readout.quick_take : locales[language].chat.result_breakdown.aria_label)}</h2><img alt="Actual Argus ${escape(surface)} frame" src="data:image/png;base64,${fs.readFileSync(framePath).toString('base64')}">${rejected ? `<div class="diagnostic"><h2>DIAGNOSTIC ONLY: rejected/unavailable raw draft</h2><p>Never accepted or displayed inside the product frame. Complete provider content follows without edits.</p>${raw}</div>` : ''}${webSources}</section><section><h2>CANONICAL SOURCE NUMBERS</h2><p class="note">Exact stored values and paths. No recomputation or rounding. Full chart points and trades remain in the unchanged source JSON cited above. DCA source came from direct engine execution, not a successful DCA chat journey.</p><table>${pair.source_numbers.map(row => `<tr><td>${escape(row.path)}</td><td>${escape(JSON.stringify(row.value))}</td></tr>`).join('')}</table></section></main></html>`;
        fs.writeFileSync(path.join(output, `${name}.html`), html);
        const sheet = await context.newPage();
        await sheet.setViewportSize({ width: 1900, height: 1200 });
        await sheet.setContent(html);
        await sheet.screenshot({ path: path.join(output, `${name}.png`), fullPage: true });
        await sheet.close();
        outcomes.push({ name, language, surface, provider: outcome.provider, accepted: outcome.accepted, visible_text: visible, rendered_links: renderedLinks, screenshot: `${name}.png`, frame_screenshot: `${name}-frame.png`, clipboard_parity: true });
      }
      await page.reload();
      await frame('breakdown').waitFor();
      for (const surface of ['quick_take', 'breakdown']) assert(await body(surface).innerText() === before[surface], 'Reload changed saved text');
    }
    const final = await (await fetch(`${api}/replay-proof`)).json();
    assert(outcomes.length === 12, 'Expected exactly twelve outcomes');
    assert(!blocked.length && !errors.length && !consoleEntries.length, 'Browser network/console/page issue');
    assert(!final.blocked_network.length && !final.blocked_mutations.length && final.stored_artifacts_unchanged, 'API guard or immutability issue');
    for (const [file, expected] of Object.entries({ ...webSource.tracked_source_sha256, ...seed.loaded_reader_hashes })) assert(hash(file) === expected, `Source changed during capture: ${file}`);
    for (const pair of seed.cases) assert(hash(pair.source_path) === pair.source.sha256, 'Canonical fixture changed');
    fs.writeFileSync(path.join(output, 'proof.json'), JSON.stringify({
      status: 'passed', captured_at: new Date().toISOString(), reader_sha: seed.reader_sha,
      measurement_checkouts: seed.measurement_checkouts, report_sha256: seed.report_sha256,
      synthetic_browser_preflight: seed.synthetic_browser_preflight,
      browser: 'Chromium via existing repository Playwright; Browser plugin not available',
      viewport: { width: 1440, height: 1100 }, evidence_sheet_width: 1900,
      outcomes, console_entries: consoleEntries, page_errors: errors, blocked_requests: blocked,
      api_requests: requests, provider_calls: 0, backtests: 0, market_data_calls: 0,
      stored_artifacts_unchanged: final.stored_artifacts_unchanged,
      stored_artifacts_sha256: final.stored_artifacts_sha256,
      reader_hashes: seed.loaded_reader_hashes, fixture_sha256: seed.fixture_sha256,
    }, null, 2) + '\n');
    console.log(JSON.stringify({ status: 'passed', outcomes: outcomes.length, output, provider_calls: 0 }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
