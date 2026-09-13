async (page) => {
  const input = __QA_INPUT__;
  const records = [];
  let publications = 0;
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/public-excerpt')) publications++;
  });
  for (const width of [390, 1280]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await page.goto(`http://127.0.0.1:3319${input.path}`, { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: input.copy.selection.title, exact: true }).click();
    const dialog = page.getByRole('dialog', { name: input.copy.selection.title, exact: true });
    await dialog.getByRole('checkbox').first().waitFor();
    const turns = [];
    for (const item of input.turns) {
      const row = dialog.locator('li').filter({ hasText: item.question });
      const checkbox = row.getByRole('checkbox');
      await checkbox.waitFor();
      const disabled = await checkbox.isDisabled();
      const reason = await checkbox.evaluate(node => node.getAttribute('aria-describedby') ? document.getElementById(node.getAttribute('aria-describedby'))?.textContent : null);
      if (disabled === input.expectedEligible) throw new Error(`${item.case}: unexpected eligibility`);
      if (!input.expectedEligible && reason !== input.copy.selection.reasons.unsupported_backtest) throw new Error(`${item.case}: missing localized reason`);
      await row.scrollIntoViewIfNeeded();
      await page.screenshot({ path: `${input.output}/incomplete-${item.case}-${width}-${input.language}.png`, scale: 'css' });
      turns.push({ case: item.case, question: item.question, disabled, reason });
    }
    records.push({ width, language: input.language, turns });
    await page.keyboard.press('Escape');
    await dialog.waitFor({ state: 'hidden' });
  }
  if (publications) throw new Error('Inspecting incomplete turns created a link');
  return { records, publications };
}
