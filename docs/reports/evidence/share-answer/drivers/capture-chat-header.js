async (page) => {
  const input = __QA_INPUT__;
  const records = [];
  for (const width of [390, 1280]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await page.goto(`http://127.0.0.1:3319${input.path}`, { waitUntil: 'networkidle' });
    const share = page.getByRole('button', { name: input.copy.selection.title, exact: true });
    await share.waitFor();
    await page.mouse.move(0, 0);
    await page.screenshot({ path: `${input.output}/${input.name}-header-${width}.png`, scale: 'css' });
    records.push({ width, headerControls: await share.count(), sharePills: await page.getByRole('button', { name: /^(Share this|Compartir esto)/ }).count(), overflow: await page.evaluate(() => document.documentElement.scrollWidth > innerWidth) });
  }
  return records;
}
