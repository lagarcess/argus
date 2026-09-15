import { expect, test } from "@playwright/test";
import { activity, installActivityFixture, refreshActivity, captureEvidence } from "./support/conversation-activity-fixture";

for (const language of ["en", "es-419"] as const) {
  for (const mode of ["hidden", "visible", "anchor"] as const) {
    test(`saved-message freshness: ${mode} observer misses all working states (${language})`, async ({ context, page: tabA }) => {
      const fixture = await installActivityFixture(context, {
        language, longTranscripts: mode === "anchor" ? ["activity-a"] : [],
        activities: mode !== "hidden" ? { "activity-b": activity("running") } : {},
      });
      const tabB = await context.newPage();
      fixture.hideWorkingFrom.add(tabB);
      const anchor = "activity-a-assistant-3";
      const route = `/chat?conversation=activity-a${mode === "anchor" ? `&message=${anchor}` : ""}`;
      for (const tab of [tabA, tabB]) {
        await tab.goto(route);
        await expect(tab.getByTestId("chat-input")).toBeVisible();
        await expect(tab.getByText(/Transcript activity-a message 0/, { exact: false }).first()).toHaveCount(1);
      }
      if (mode === "hidden") {
        await tabB.evaluate(() => {
          Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
          document.dispatchEvent(new Event("visibilitychange"));
        });
      }
      const beforeURL = tabB.url();
      const transcript = tabB.getByTestId("conversation-transcript-region");
      const scrollTop = await transcript.evaluate((element) => {
        if (element.scrollHeight > element.clientHeight) element.scrollTop = 240;
        element.dispatchEvent(new Event("scroll"));
        return element.scrollTop;
      });

      const newReads: string[] = [];
      for (const [tab, name] of [[tabA, "A"], [tabB, "B"]] as const) tab.on("request", (request) => { if (request.url().includes("/messages")) newReads.push(name); });
      const prompt = language === "en" ? "What is compound interest?" : "¿Qué es el interés compuesto?";
      await tabA.getByTestId("chat-input").fill(prompt);
      await tabA.getByTestId("chat-send").click();
      await expect.poll(() => fixture.pendingStreams.has("activity-a")).toBe(true);
      const reads = fixture.messageRequests.length;
      newReads.length = 0;
      fixture.settleOrdinary("activity-a", "none");
      // Plain saved assistant message, with neither a job nor unread cursor.
      fixture.activities["activity-a"] = activity();
      expect(fixture.jobs).toEqual({});
      await expect(tabA.getByText("Terminal response for activity-a", { exact: true })).toHaveCount(1);
      if (mode === "hidden") {
        await expect(tabB.getByText("Terminal response for activity-a", { exact: true })).toHaveCount(0);
        await tabB.evaluate(() => {
          Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
          document.dispatchEvent(new Event("visibilitychange"));
          window.dispatchEvent(new Event("focus"));
        });
      }
      // Visible cases receive their next existing activity poll through another
      // loaded conversation. The active conversation always projects idle.
      try {
        await expect(tabB.getByText("Terminal response for activity-a", { exact: true })).toHaveCount(1, { timeout: 10_000 });
        expect(tabB.url()).toBe(beforeURL);
        await expect.poll(() => transcript.evaluate((element) => element.scrollTop)).toBeCloseTo(scrollTop, 0);
        expect({ total: fixture.messageRequests.length, newReads }).toEqual({ total: reads + 1, newReads: ["B"] });
        await refreshActivity(tabB, fixture);
        expect({ total: fixture.messageRequests.length, newReads }).toEqual({ total: reads + 1, newReads: ["B"] });
      } finally {
        await captureEvidence(tabB, `598-v2-${mode}-${language}.png`);
      }
    });
  }
}

for (const language of ["en", "es-419"] as const) {
  test(`unanswered user keeps the idle observer checking until the reply lands (${language})`, async ({ context, page: tabA }) => {
    const fixture = await installActivityFixture(context, { language });
    const tabB = await context.newPage();
    fixture.hideWorkingFrom.add(tabB);
    for (const tab of [tabA, tabB]) {
      await tab.goto("/chat?conversation=activity-a");
      await expect(tab.getByTestId("chat-input")).toBeVisible();
      await expect(tab.getByText("Transcript activity-a message 0", { exact: true })).toHaveCount(1);
    }
    const prompt = language === "en" ? "What is compound interest?" : "¿Qué es el interés compuesto?";
    await tabA.getByTestId("chat-input").fill(prompt);
    await tabA.getByTestId("chat-send").click();
    await expect.poll(() => fixture.pendingStreams.has("activity-a")).toBe(true);
    // The split read sees idle operation followed by the newly persisted user.
    fixture.persistOrdinaryUser("activity-a");
    await refreshActivity(tabB, fixture);
    await expect(tabB.getByText(prompt, { exact: true })).toHaveCount(1);
    const readsAfterUser = fixture.messageRequests.length;
    // The normal activity loop is idle. No focus/activity event follows this save.
    fixture.settleOrdinary("activity-a", "none");
    try {
      await expect(tabB.getByText("Terminal response for activity-a", { exact: true })).toHaveCount(1, { timeout: 10_000 });
      await expect(tabA.getByText("Terminal response for activity-a", { exact: true })).toHaveCount(1);
      await expect(tabB.getByText(prompt, { exact: true })).toHaveCount(1);
      expect(fixture.messageRequests.length).toBeGreaterThan(readsAfterUser);
      const settledReads = fixture.messageRequests.length;
      await tabB.waitForTimeout(2_500);
      expect(fixture.messageRequests.length).toBe(settledReads);
    } finally {
      await captureEvidence(tabB, `598-v3-interleaving-${language}.png`);
    }
  });
}
