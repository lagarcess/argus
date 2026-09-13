async (page) => {
  const input = __QA_INPUT__;
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`http://127.0.0.1:3319${input.path}`, { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: input.settings, exact: true }).click();
  await page.getByRole('button', { name: input.preferences, exact: true }).click();
  await page.getByRole('button', { name: input.languageLabel, exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: input.choice }).click();
  await page.getByRole('button', { name: input.nextShareLabel, exact: true }).waitFor();
  return { changedThroughSettings: true, language: input.nextLanguage };
}
