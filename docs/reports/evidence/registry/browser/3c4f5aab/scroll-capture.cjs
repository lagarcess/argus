const fs = require("node:fs");
const base = "/Users/garces/.codex/worktrees/aa72/private-alpha-next/web/node_modules/playwright-core/lib/client";
const { Locator } = require(`${base}/locator.js`);
const { Page } = require(`${base}/page.js`);
const logPath = "/private/tmp/registry-browser-3c4f5aab/scroll-captures.jsonl";
const record = (data) => fs.appendFileSync(logPath, `${JSON.stringify(data)}\n`);

async function position(page, card, path, height) {
  const originalViewport = page.viewportSize();
  if (height) await page.setViewportSize({ width: originalViewport.width, height });
  const scroll = await card.evaluate(async (element) => {
    const region = document.querySelector('[data-testid="conversation-transcript-region"]');
    const before = { scrollTop: region.scrollTop, cardTop: element.getBoundingClientRect().top };
    region.scrollBy(0, before.cardTop - 160);
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const bounds = element.getBoundingClientRect();
    return { before, after: { scrollTop: region.scrollTop, cardTop: bounds.top, cardBottom: bounds.bottom, cardHeight: bounds.height } };
  });
  record({ path, originalViewport, viewport: page.viewportSize(), requestedCardTop: 160, actualScroll: scroll });
}

const locatorScreenshot = Locator.prototype.screenshot;
Locator.prototype.screenshot = async function(options = {}) {
  const path = options.path ?? "";
  if (path.includes("tool-card-") || path.includes("tool-backtest-")) {
    await position(this.page(), this, path, path.includes("tool-backtest-") ? 1500 : null);
  }
  return locatorScreenshot.call(this, options);
};

const pageScreenshot = Page.prototype.screenshot;
Page.prototype.screenshot = async function(options = {}) {
  const path = options.path ?? "";
  if (path.includes("tool-jobs-") || path.includes("tool-history-")) {
    await position(this, this.locator("[data-tool-result-card]").first(), path, path.includes("tool-jobs-") ? 1500 : 900);
  }
  return pageScreenshot.call(this, options);
};
