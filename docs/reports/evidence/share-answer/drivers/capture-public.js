async (page) => {
  const input = __QA_INPUT__;
  const records = [];
  const failures = [];
  page.on('pageerror', error => failures.push(error.message));
  await page.context().clearCookies();
  await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' });
  for (const language of ['en', 'es-419']) {
    await page.context().setExtraHTTPHeaders({ 'Accept-Language': language });
    for (const width of [390, 1280]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
      const response = await page.goto(`http://127.0.0.1:3319${input.path}`, { waitUntil: 'networkidle' });
      await page.evaluate(() => document.fonts.ready);
      await page.mouse.move(0, 0);
      const tag = `${input.name}-${width}-${language}`;
      await page.screenshot({ path: `${input.output}/${tag}.png`, fullPage: true, scale: 'css' });
      await page.screenshot({ path: `${input.output}/${tag}-fold.png`, scale: 'css' });
      records.push({
        tag, language, width, status: response.status(),
        text: await page.locator('body').innerText(),
        cookies: await page.context().cookies(),
        metadata: await page.evaluate(() => ({
          robots: document.querySelector('meta[name="robots"]')?.content,
          overflow: document.documentElement.scrollWidth > innerWidth,
          title: document.title,
          canonical: document.querySelector('link[rel="canonical"]')?.href,
          image: document.querySelector('meta[property="og:image"]')?.content,
          contentLanguages: [...document.querySelectorAll('main [lang]')].map(node => node.lang),
          links: [...document.querySelectorAll('a[href]')].map(node => ({ text: node.textContent.trim(), href: node.getAttribute('href') })),
        })),
      });
    }
  }
  return { records, pageErrors: failures };
}
