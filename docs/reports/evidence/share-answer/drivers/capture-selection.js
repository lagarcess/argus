async (page) => {
  const input = __QA_INPUT__;
  const copy = input.copy;
  const records = [];
  let publications = 0;
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/public-excerpt')) publications++;
  });
  for (const width of [390, 1280]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await page.goto(`http://127.0.0.1:3319${input.path}`, { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: copy.selection.title, exact: true }).click();
    const dialog = page.getByRole('dialog', { name: copy.selection.title, exact: true });
    await dialog.getByRole('checkbox').first().waitFor();
    const all = dialog.getByRole('button', { name: copy.selection.all, exact: true });
    const allEnabled = await all.isEnabled();
    if (allEnabled) await all.click();
    else {
      const eligible = dialog.locator('input[type="checkbox"]:not(:disabled):not(:checked)');
      for (let i = 0; i < 4; i++) await eligible.nth(0).check();
    }
    const choices = await dialog.locator('input[type="checkbox"]').evaluateAll(nodes => nodes.map(node => ({
      question: node.parentElement?.textContent?.trim(), checked: node.checked, disabled: node.disabled,
      reason: node.getAttribute('aria-describedby') ? document.getElementById(node.getAttribute('aria-describedby'))?.textContent : null,
    })));
    const tag = `${input.name}-${width}-${input.language}`;
    await page.screenshot({ path: `${input.output}/${tag}.png`, scale: 'css' });
    const refused = dialog.locator('li').filter({ has: page.locator('input:disabled') });
    await refused.first().scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${input.output}/${tag}-reasons.png`, scale: 'css' });
    await refused.last().scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${input.output}/${tag}-fields.png`, scale: 'css' });
    let noteRefusal = null;
    if (input.unsafeNote) {
      await dialog.getByRole('textbox', { name: copy.owner.note_label, exact: true }).fill(input.unsafeNote);
      const pending = page.waitForResponse(response => response.url().endsWith('/public-excerpt-preview') && response.request().method() === 'POST');
      await dialog.getByRole('button', { name: copy.selection.preview, exact: true }).click();
      const response = await pending;
      const alert = dialog.getByRole('alert');
      await alert.scrollIntoViewIfNeeded();
      noteRefusal = { status: response.status(), text: await alert.innerText() };
      if (response.status() !== 422 || !noteRefusal.text.includes(copy.selection.fields.owner_note)) throw new Error('Missing field-specific note refusal');
      await page.screenshot({ path: `${input.output}/${tag}-note.png`, scale: 'css' });
    }
    records.push({ tag, width, language: input.language, allEnabled, choices, noteRefusal, overflow: await page.evaluate(() => document.documentElement.scrollWidth > innerWidth) });
    await page.keyboard.press('Escape');
    await dialog.waitFor({ state: 'hidden' });
  }
  if (publications) throw new Error('Inspecting/refusing selection published a receipt');
  return { records, publications };
}
