import { expect, test } from "@playwright/test";
import { CONVERSATIONS, installMobileShellFixture } from "./support/mobile-shell-fixture";

// Run with the existing sharing flag explicitly enabled in the test server.
test.skip(process.env.NEXT_PUBLIC_EVIDENCE_RECEIPT_SHARING_ENABLED !== "true", "Sharing remains default off.");

for (const width of [390, 1280]) {
  test(`sharing at ${width}px owns one history entry and returns header focus`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await installMobileShellFixture(page, { account: "registered" });
    await page.route("**/public-excerpt-candidates", (route) => route.fulfill({
      json: { max_turns: 4, items: [{ message_id: "result-answer", question: "How did this idea perform?", kind: "backtest", eligible: true }] },
    }));
    let publications = 0;
    page.on("request", (request) => {
      if (request.method() === "POST" && /public-excerpt$/.test(request.url())) publications += 1;
    });
    await page.goto(`/chat?conversation=${CONVERSATIONS[0].id}`);
    const opener = page.getByRole("button", { name: "Share conversation", exact: true });
    await expect(opener).toBeVisible();
    await page.evaluate(() => {
      const trace = { pushes: 0, backs: 0 };
      Object.assign(window, { receiptFocusTrace: trace });
      const push = window.history.pushState.bind(window.history);
      const back = window.history.back.bind(window.history);
      window.history.pushState = (...args) => { trace.pushes += 1; push(...args); };
      window.history.back = () => { trace.backs += 1; back(); };
    });
    for (const cycle of [1, 2]) {
      await opener.click();
      const dialog = page.getByRole("dialog", { name: "Share conversation", exact: true });
      await expect(dialog.getByRole("checkbox")).toBeVisible();
      // Flush the effect cleanup tick that used to pop the temporary desktop
      // dialog while its replacement phone sheet was still open.
      await page.evaluate(() => new Promise<void>((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(resolve, 0)));
      }));
      const trace = () => page.evaluate(() => (window as unknown as { receiptFocusTrace: { pushes: number; backs: number } }).receiptFocusTrace);
      expect(await trace()).toEqual({ pushes: cycle, backs: cycle - 1 });
      await page.keyboard.press("Escape");
      await expect(dialog).toBeHidden();
      await expect.poll(trace).toEqual({ pushes: cycle, backs: cycle });
      await expect(opener).toBeFocused();
    }
    expect(publications).toBe(0);
  });
}
