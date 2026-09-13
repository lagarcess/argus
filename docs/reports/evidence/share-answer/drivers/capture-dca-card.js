async (page) => {
  const input = __QA_INPUT__;
  const records = [];
  for (const width of [390, 1280]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await page.goto(`http://127.0.0.1:3319${input.path}`, { waitUntil: 'networkidle' });
    const card = page.getByRole('region', { name: 'Hero + Delta Evidence Card', exact: true });
    await card.waitFor();
    await card.locator('summary').click();
    await card.locator('details dl').scrollIntoViewIfNeeded();
    const details = await card.locator('details').innerText();
    if (!details.includes('200') || !details.includes('0')) throw new Error('DCA amounts are missing from card details');
    await page.evaluate(() => document.fonts.ready);
    await page.mouse.move(0, 0);
    await page.screenshot({ path: `${input.output}/dca-card-${width}-${input.language}.png`, scale: 'css' });
    records.push({
      width, language: input.language, details, text: await card.innerText(),
      headerControls: await page.getByRole('button', { name: input.copy.selection.title, exact: true }).count(),
      cardShareControls: await card.getByRole('button', { name: /share|compartir/i }).count(),
      overflow: await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),
    });
  }
  return records;
}
