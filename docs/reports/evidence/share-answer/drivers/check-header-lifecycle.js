async (page) => {
  const input = __QA_INPUT__;
  const records = [];
  await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' });
  for (const width of [390, 1280]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto(`http://127.0.0.1:3319${input.path}`, { waitUntil: 'networkidle' });
    const opener = page.getByRole('button', { name: 'Share conversation', exact: true });
    await opener.waitFor();
    await page.evaluate(() => {
      const trace = { pushes: 0, backs: 0 };
      window.receiptFocusTrace = trace;
      const push = history.pushState.bind(history);
      const back = history.back.bind(history);
      history.pushState = (...args) => { trace.pushes++; push(...args); };
      history.back = () => { trace.backs++; back(); };
    });
    const cycles = [];
    for (const cycle of [1, 2]) {
      await opener.click();
      const dialog = page.getByRole('dialog', { name: 'Share conversation', exact: true });
      await dialog.getByRole('checkbox').first().waitFor();
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(resolve, 0)))));
      const opened = await page.evaluate(() => ({ ...window.receiptFocusTrace }));
      await page.keyboard.press('Escape');
      await dialog.waitFor({ state: 'hidden' });
      await page.waitForFunction(() => document.activeElement?.getAttribute('aria-label') === 'Share conversation');
      await page.waitForFunction(expected => window.receiptFocusTrace.backs === expected, cycle);
      const closed = await page.evaluate(() => ({ ...window.receiptFocusTrace }));
      if (opened.pushes !== cycle || opened.backs !== cycle - 1 || closed.backs !== cycle) throw new Error(`Overlay ownership failed at ${width}px cycle ${cycle}: ${JSON.stringify({opened,closed})}`);
      cycles.push({ cycle, opened, closed, focusReturned: true });
    }
    records.push({ width, headerControls: await opener.count(), persistentSharePills: await page.getByRole('button', { name: /^Share this/ }).count(), cycles });
  }
  return records;
}
