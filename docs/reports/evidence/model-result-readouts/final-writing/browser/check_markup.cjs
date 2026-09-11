/* Free server-rendered Markdown check. No browser, server, provider or URL fetch. */
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { execFileSync } = require('node:child_process');

(async () => {
  global.fetch = () => { throw new Error('Offline check prohibits fetch'); };
  for (const module of ['node:http', 'node:https']) {
    require(module).request = () => { throw new Error('Offline check prohibits HTTP'); };
    require(module).get = () => { throw new Error('Offline check prohibits HTTP'); };
  }
  const root = process.cwd();
  const report = JSON.parse(execFileSync(path.join(root, '.venv/bin/python'), ['-c',
    'import json,sys; from pathlib import Path; sys.path.insert(0, "docs/reports/evidence/model-result-readouts/final-writing/browser"); from replay_data import synthetic_report; print(json.dumps(synthetic_report(Path.cwd())))',
  ], { encoding: 'utf8', env: { PATH: process.env.PATH, PYTHONDONTWRITEBYTECODE: '1' } }));
  const React = require(path.join(root, 'web/node_modules/react'));
  const { renderToStaticMarkup } = require(path.join(root, 'web/node_modules/react-dom/server'));
  const { default: ReactMarkdown } = await import(pathToFileURL(require.resolve(path.join(root, 'web/node_modules/react-markdown'))));
  const { default: remarkGfm } = await import(pathToFileURL(require.resolve(path.join(root, 'web/node_modules/remark-gfm'))));
  let checked = 0;
  for (const pair of report.results) {
    const outcome = pair.breakdown;
    // Both accepted and rejected synthetic bodies test parsing only. Rejected
    // content still remains diagnostic in the separate production-frame harness.
    const response = pair.provider_responses.find(item => item.task === 'result_breakdown');
    const text = JSON.parse(response.raw_drafts[0]).text;
    const html = renderToStaticMarkup(React.createElement(ReactMarkdown, { remarkPlugins: [remarkGfm] }, text));
    const url = outcome.sources[0].url;
    assert(html.includes(`href="${url.replaceAll('&', '&amp;')}"`));
    assert.equal((html.match(/<a /g) || []).length, 1);
    assert(!html.includes('href="javascript:'));
    checked += 1;
  }
  console.log(JSON.stringify({ status: 'passed', synthetic_citation_markup_cases: checked, provider_calls: 0, browsers_started: 0, servers_started: 0 }));
})().catch(error => { console.error(error); process.exitCode = 1; });
