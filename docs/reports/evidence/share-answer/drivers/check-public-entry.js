async (page) => {
  const input = __QA_INPUT__;
  const events = [];
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/public/receipt-funnel')) events.push({ method: request.method(), resourceType: request.resourceType() });
  });
  await page.context().clearCookies();
  await page.context().setExtraHTTPHeaders({ 'Accept-Language': 'en' });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`http://127.0.0.1:3319${input.path}`, { waitUntil: 'networkidle' });
  const cta = page.getByRole('link', { name: 'Continue with Argus', exact: true });
  const href = await cta.getAttribute('href');
  if (href !== '/') throw new Error('Public action carries state');
  const before = [...events];
  if (before.length !== 1) throw new Error('Incorrect viewed event');
  await cta.click();
  await page.waitForURL(url => url.pathname === '/' && !url.search);
  await page.getByText(/By messaging Argus/).first().waitFor();
  await page.waitForURL(url => url.pathname === '/chat' && !url.search);
  const entry = await page.evaluate(() => ({ path: location.pathname, query: location.search, fragment: location.hash, assistantTurns: document.querySelectorAll('[data-assistant-message-id]').length, composer: [...document.querySelectorAll('textarea, [contenteditable="true"]')].map(node => node.value ?? node.textContent) }));
  if (entry.assistantTurns || entry.composer.some(value => value)) throw new Error('Public action prefilled a prompt');
  await page.screenshot({ path: `${input.output}/continue-guest-entry.png`, scale: 'css' });
  return { href, entry, eventRequestsBeforeClick: before.length, eventRequestsAfterClick: events.length, note: 'The browser bridge omits sendBeacon Blob bodies. Typed event payloads are covered by focused tests; these are observed request counts.' };
}
