async (page) => {
  const input = __QA_INPUT__;
  const copy = input.copy;
  const requests = [];
  page.on('request', request => {
    if (/public-excerpt(?:-preview)?$/.test(request.url()) && request.method() === 'POST') {
      requests.push({ phase: request.url().endsWith('-preview') ? 'preview' : 'publish', method: request.method() });
    }
  });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`http://127.0.0.1:3319${input.path}`, { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: copy.selection.title, exact: true }).click();
  const dialog = page.getByRole('dialog', { name: copy.selection.title, exact: true });
  await dialog.getByRole('checkbox').first().waitFor();
  if (input.select === 'all') await dialog.getByRole('button', { name: copy.selection.all, exact: true }).click();
  else if (input.selectIndices) {
    for (const index of input.selectIndices) await dialog.getByRole('checkbox').nth(index).check();
  } else await dialog.getByRole('checkbox').first().check();
  const selected = await dialog.locator('input[type="checkbox"]:checked').count();
  if (requests.some(item => item.phase === 'publish')) throw new Error('Selection published prematurely');
  const previewResponse = page.waitForResponse(response => response.url().endsWith('/public-excerpt-preview') && response.request().method() === 'POST');
  await dialog.getByRole('button', { name: copy.selection.preview, exact: true }).click();
  const preview = await previewResponse;
  if (preview.status() !== 200) throw new Error(`Preview returned ${preview.status()}`);
  await dialog.locator('main').waitFor();
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: `${input.output}/${input.name}-preview.png`, scale: 'css' });
  const previewText = await dialog.locator('main').innerText();
  if (requests.some(item => item.phase === 'publish')) throw new Error('Preview published prematurely');
  const publicationResponse = page.waitForResponse(response => response.url().endsWith('/public-excerpt') && response.request().method() === 'POST');
  const button = dialog.getByRole('button', { name: copy.owner.create, exact: true });
  if (await button.count()) await button.click();
  else await dialog.getByRole('button', { name: copy.selection.reuse, exact: true }).click();
  const publication = await publicationResponse;
  if (publication.status() !== 200 && publication.status() !== 201) throw new Error(`Creation returned ${publication.status()}`);
  const link = dialog.getByRole('textbox', { name: copy.owner.copy, exact: true });
  await link.waitFor();
  await page.screenshot({ path: `${input.output}/${input.name}-created.png`, scale: 'css' });
  return { selected, previewStatus: preview.status(), createStatus: publication.status(), requests, previewText, receipt: (await publication.json()).receipt, link: await link.inputValue() };
}
