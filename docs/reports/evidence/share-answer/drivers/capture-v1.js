async (page) => {
  const input = __QA_INPUT__;
  const root = input.output;
  const phase = input.phase;
  const records = [];
  await page.context().clearCookies();
  await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' });
  for (const language of ['en', 'es-419']) {
    await page.context().setExtraHTTPHeaders({ 'Accept-Language': language });
    for (const width of [390, 1280]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
      const response = await page.goto(`http://127.0.0.1:3319${input.path}`, { waitUntil: 'networkidle' });
      await page.locator('canvas').first().waitFor({ state: 'visible' });
      await page.evaluate(() => document.fonts.ready);
      await page.mouse.move(0, 0);
      const main = page.locator('main');
      const tag = `v1-${phase}-${width}-${language}`;
      // The receipt body is the frozen regression surface. The separately tested
      // action bar intentionally gains the founder's new CTA copy in this lane.
      await main.screenshot({
        path: `${root}/${tag}.png`, scale: 'css',
        style: '.fixed, nextjs-portal { visibility: hidden !important; }',
      });
      records.push({
        tag, language, width, status: response.status(),
        html: await main.innerHTML(),
        text: await main.innerText(),
        box: await main.boundingBox(),
        cookies: await page.context().cookies(),
        metadata: await page.evaluate(() => ({
          language: document.querySelector('main').parentElement.lang,
          robots: document.querySelector('meta[name="robots"]')?.content,
          overflow: document.documentElement.scrollWidth > innerWidth,
        })),
      });
    }
  }
  return records;
}
