import { expect, test } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import { installMobileShellFixture } from './checkout/web/e2e/support/mobile-shell-fixture';
import en from './checkout/web/public/locales/en/common.json';
import es from './checkout/web/public/locales/es-419/common.json';

const root = '/private/tmp/registry-rowless-browser-c6c28fef';
const fixture = JSON.parse(readFileSync(`${root}/fixture.json`, 'utf8'));
const conversationId = 'conversation-alpha';
for (const language of ['en', 'es-419'] as const) {
  test(`rowless completed research narrative and sources survive reload: ${language}`, async ({ page }) => {
    const facts = fixture[language];
    const api: { method: string; path: string; interception: string }[] = [];
    const blocked: string[] = [];
    const errors: string[] = [];
    const requests: string[] = [];
    const phases: object[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('request', (request) => requests.push(request.url()));
    await page.route('**/*', async (route) => {
      const url = new URL(route.request().url());
      if (url.origin === 'http://127.0.0.1:3193') return route.continue();
      blocked.push(url.toString());
      return route.abort('blockedbyclient');
    });
    await installMobileShellFixture(page, { language, theme: 'light', account: 'registered' });
    await page.route(`**/api/v1/conversations/${conversationId}/messages**`, (route) => route.fulfill({
      json: { items: [
        { id: `question-${language}`, role: 'user', content: facts.question, created_at: '2026-09-10T05:00:00Z', metadata: {} },
        { id: `answer-${language}`, role: 'assistant', content: '', created_at: '2026-09-10T05:00:01Z', metadata: { tool_result_cards: [facts.card] } },
      ], next_cursor: null },
    }));
    await page.route('**/api/v1/**', async (route) => {
      const path = new URL(route.request().url()).pathname;
      api.push({ method: route.request().method(), path, interception: 'fulfilled by authored transcript or established mobile-shell fixture' });
      if (/chat\/stream|recompute|backtest|research|public-excerpt|public\/receipts/.test(path)) {
        throw new Error(`Unexpected execution/publication API request: ${path}`);
      }
      return route.fallback();
    });
    try {
      await page.goto(`/chat?conversation=${conversationId}`, { waitUntil: 'networkidle' });
      const card = page.locator('[data-tool-result-card="research"]');
      const copy = language === 'en' ? en : es;
      for (const phase of ['initial', 'reload']) {
        if (phase === 'reload') await page.reload({ waitUntil: 'networkidle' });
        await expect(card).toHaveCount(1);
        await expect(card.getByText(facts.narrative, { exact: true })).toBeVisible();
        await expect(card.getByRole('heading', { name: copy.chat.tools.research.title, exact: true })).toBeVisible();
        await expect(card.locator('[data-tool-answer]')).toHaveCount(0);
        const disclosure = card.locator('summary');
        await expect(disclosure).toContainText(language === 'en' ? '2 sources' : '2 fuentes');
        await disclosure.click();
        for (const source of facts.sources) {
          const link = card.locator(`a[href="${source.url}"]`);
          await expect(link).toBeVisible();
          await expect(link).toContainText(source.title);
        }
        await expect(card.getByText(facts.question, { exact: true })).toBeVisible();
        await expect(card.locator('input, select')).toHaveCount(0);
        phases.push({ phase, narrative: await card.innerText(), source_hrefs: await card.locator('a').evaluateAll((links) => links.map((link) => (link as HTMLAnchorElement).href)) });
      }
      await card.scrollIntoViewIfNeeded();
      await page.screenshot({ path: `${root}/rowless-${language}.png`, animations: 'disabled' });
      await card.screenshot({ path: `${root}/rowless-card-${language}.png`, animations: 'disabled' });
      expect(errors).toEqual([]);
      expect(blocked).toEqual([]);
      expect(api.filter((entry) => entry.path.endsWith('/messages')).length).toBeGreaterThanOrEqual(2);
    } finally {
      writeFileSync(`${root}/network-${language}.json`, JSON.stringify({ api, blocked, requests, page_errors: errors, phases }, null, 2));
    }
  });
}
