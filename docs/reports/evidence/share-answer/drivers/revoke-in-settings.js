async (page) => {
  const input = __QA_INPUT__;
  const copy = input.copy;
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`http://127.0.0.1:3319${input.path}`, { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: input.settings, exact: true }).click();
  await page.getByRole('button', { name: input.data, exact: true }).click();
  await page.getByRole('button', { name: copy.list.menu, exact: true }).click();
  const dialog = page.getByRole('dialog', { name: copy.list.title, exact: true });
  const row = dialog.locator('li').filter({ has: page.locator(`a[href="${input.publicPath}"]`) });
  await row.waitFor();
  await row.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${input.output}/${input.name}-before.png`, scale: 'css' });
  const before = await dialog.innerText();
  await row.getByRole('button', { name: copy.list.revoke, exact: true }).click();
  const responsePromise = page.waitForResponse(response => response.request().method() === 'DELETE' && response.url().includes('/public-excerpts/'));
  await row.getByRole('button', { name: copy.list.confirm_revoke, exact: true }).click();
  const response = await responsePromise;
  if (response.status() !== 200) throw new Error(`Revoke returned ${response.status()}`);
  await dialog.locator(`a[href="${input.publicPath}"]`).waitFor({ state: 'hidden' });
  await page.screenshot({ path: `${input.output}/${input.name}-after.png`, scale: 'css' });
  return { before, after: await dialog.innerText(), status: response.status(), payload: await response.json() };
}
