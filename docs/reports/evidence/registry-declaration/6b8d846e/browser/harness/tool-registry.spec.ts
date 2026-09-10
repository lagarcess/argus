import { installRegistryEvidenceHooks } from "./registry-evidence-hooks";
installRegistryEvidenceHooks();
import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Route } from "@playwright/test";
import { installMobileShellFixture } from "./support/mobile-shell-fixture";
import type { ApiMessage } from "../lib/argus-api";
import type { ToolProgress, ToolResultCard } from "../lib/tool-result-card";
import type { ToolJob } from "../components/chat/types";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";

const fixtureRoot = path.resolve(__dirname, "../../docs/reports/evidence/registry");
const cards = JSON.parse(readFileSync(path.join(fixtureRoot, "tool-cards.json"), "utf8")) as Record<string, ToolResultCard>;
const progress = JSON.parse(readFileSync(path.join(fixtureRoot, "tool-progress.json"), "utf8")) as ToolProgress;
const backtests = JSON.parse(readFileSync(path.join(fixtureRoot, "backtest-cards.json"), "utf8")) as Record<string, { card: ToolResultCard }>;
const conversationId = "conversation-alpha";
const message = (role: "user" | "assistant", id: string, content: string, metadata: Record<string, unknown> = {}): ApiMessage => ({
  id, role, content, metadata, conversation_id: conversationId, created_at: "2026-09-09T15:10:00Z",
});
const json = (route: Route, body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });

for (const language of ["en", "es-419"] as const) {
  test(`a later saved user message makes old tool inputs read-only ${language}`, async ({ page }) => {
    await installMobileShellFixture(page, { language, theme: "light" });
    const transcript = [message("assistant", "tool-message", "", { tool_result_cards: [cards.initial] }), message("user", "later-user", "A later saved message")];
    await page.route(`**/api/v1/conversations/${conversationId}/messages**`, (route) => json(route, { items: transcript, next_cursor: null }));
    await page.goto(`/chat?conversation=${conversationId}`, { waitUntil: "networkidle" });
    const card = page.locator("[data-tool-result-card]");
    await expect(card).toHaveCount(1);
    await expect(card.locator("input, select")).toHaveCount(0);
    await expect(card.locator("#artifact-call-one-known")).toHaveText("0");
    await expect(card.locator("[data-tool-answer]")).toContainText("0");
    if (process.env.REGISTRY_SCREENSHOT_DIR) {
      mkdirSync(process.env.REGISTRY_SCREENSHOT_DIR, { recursive: true });
      await page.screenshot({ path: path.join(process.env.REGISTRY_SCREENSHOT_DIR, `tool-history-${language}.png`), animations: "disabled" });
    }
  });

  test(`sending another turn cancels the pending tool edit ${language}`, async ({ page }) => {
    await installMobileShellFixture(page, { language, theme: "light" });
    const transcript = [message("assistant", "tool-message", "", { tool_result_cards: [cards.initial] })];
    const recomputes: unknown[] = [];
    let finish!: () => void;
    const gate = new Promise<void>((resolve) => { finish = resolve; });
    await page.route("**/api/v1/**", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      if (url.pathname === `/api/v1/conversations/${conversationId}/messages`) return json(route, { items: transcript, next_cursor: null });
      if (url.pathname.endsWith("/recompute")) { recomputes.push(request.postDataJSON()); return json(route, { message: transcript[0] }); }
      if (url.pathname !== "/api/v1/chat/stream") return route.fallback();
      transcript.push(message("user", "later-user", "A later saved message"));
      await gate;
      transcript.push(message("assistant", "later-answer", "A later answer"));
      return route.fulfill({ status: 200, contentType: "text/event-stream", body: `data: ${JSON.stringify({ type: "final", payload: { message_id: "later-answer", assistant_response: "A later answer" } })}\n\ndata: [DONE]\n\n` });
    });
    await page.goto(`/chat?conversation=${conversationId}`, { waitUntil: "networkidle" });
    const card = page.locator("[data-tool-result-card]");
    await expect(card.locator("#artifact-call-one-known")).toHaveValue("0");
    await page.getByTestId("chat-input").fill("A later saved message");
    await page.clock.pauseAt(new Date());
    await card.locator("#artifact-call-one-known").fill("42");
    await page.getByTestId("chat-send").click();
    await expect(card.locator("input, select")).toHaveCount(0);
    await page.clock.runFor(600);
    expect(recomputes).toEqual([]);
    await expect(card.locator("#artifact-call-one-known")).toHaveText("0");
    finish();
    await page.clock.resume();
    await expect(page.getByText("A later answer", { exact: true })).toBeVisible();
    await page.reload({ waitUntil: "networkidle" });
    await expect(card.locator("input, select")).toHaveCount(0);
    await expect(card.locator("[data-tool-answer]")).toContainText("0");
    expect(recomputes).toEqual([]);
  });

  test(`declared backtest keeps DCA assumptions and the receipt visual ${language}`, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await installMobileShellFixture(page, { language, theme: "light" });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route(`**/api/v1/conversations/${conversationId}/messages**`, (route) => json(route, {
      items: [message("assistant", "backtest-message", "", { tool_result_cards: [backtests[language].card] })], next_cursor: null,
    }));
    await page.goto(`/chat?conversation=${conversationId}`, { waitUntil: "networkidle" });
    const card = page.locator("[data-tool-result-card]");
    const copy = (language === "en" ? en : es).receipt;
    await expect(card).toHaveCount(1);
    await expect(card.locator("[data-tool-answer]")).toContainText(copy.metric_labels.contribution_return_pct);
    await expect(card.getByText(copy.assumptions.starting_principal.replace("{{amount}}", "0"), { exact: true })).toBeVisible();
    await expect(card.getByText(copy.assumptions.recurring_contribution.replace("{{amount}}", "200"), { exact: true })).toBeVisible();
    await expect(card.getByText(copy.assumptions.modeled_fee_bps.replace("{{bps}}", "10"), { exact: true })).toBeVisible();
    await expect(card.getByText(copy.assumptions.modeled_slippage_bps.replace("{{bps}}", "5"), { exact: true })).toBeVisible();
    await expect(card.getByText(copy.cadence_values.monthly, { exact: true }).first()).toBeVisible();
    await expect(card.locator("[data-tool-visual] canvas").first()).toBeVisible();
    expect(errors).toEqual([]);
    if (process.env.REGISTRY_SCREENSHOT_DIR) {
      mkdirSync(process.env.REGISTRY_SCREENSHOT_DIR, { recursive: true });
      await card.screenshot({ path: path.join(process.env.REGISTRY_SCREENSHOT_DIR, `tool-backtest-${language}.png`), animations: "disabled" });
    }
  });

  test(`executing-call progress is localizable without another turn ${language}`, async ({ page }) => {
    await installMobileShellFixture(page, { language, theme: "light" });
    await page.addInitScript(({ progress, card }) => {
      const originalFetch = window.fetch.bind(window);
      window.fetch = async (input, init) => {
        const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
        if (!url.endsWith("/api/v1/chat/stream")) return originalFetch(input, init);
        const encoder = new TextEncoder();
        const body = new ReadableStream({ start(controller) {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "stage_start", stage: "execute", tool_progress: progress })}\n\n`));
          window.addEventListener("registry-fixture:finish", () => {
            controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "final", payload: { message_id: "progress-result", stage_outcome: "execution_succeeded", final_response_payload: { tool_result_cards: [card] } } })}\n\ndata: [DONE]\n\n`));
            controller.close();
          }, { once: true });
        } });
        return new Response(body, { headers: { "content-type": "text/event-stream" } });
      };
    }, { progress, card: cards.initial });
    await page.goto(`/chat?conversation=${conversationId}`, { waitUntil: "networkidle" });
    await page.getByTestId("chat-input").fill(language === "en" ? "Read this value." : "Lee este valor.");
    await page.getByTestId("chat-send").click();
    await expect(page.getByText(language === "en" ? "Checking 0" : "Revisando 0", { exact: true })).toBeVisible();
    await expect(page.locator("[data-tool-result-card]")).toHaveCount(0);
    if (process.env.REGISTRY_SCREENSHOT_DIR) {
      mkdirSync(process.env.REGISTRY_SCREENSHOT_DIR, { recursive: true });
      await page.screenshot({ path: path.join(process.env.REGISTRY_SCREENSHOT_DIR, `tool-progress-${language}.png`), animations: "disabled" });
    }
    await page.evaluate(() => window.dispatchEvent(new Event("registry-fixture:finish")));
    await expect(page.locator("[data-tool-result-card]")).toHaveCount(1);
  });

  for (const width of [1280, 390]) {
    test(`tool results live, recompute and reload ${language} ${width}`, async ({ page }) => {
      test.setTimeout(60_000);
      await page.setViewportSize({ width, height: 900 });
      await installMobileShellFixture(page, { language, theme: "light" });
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      let transcript: ApiMessage[] = [message("assistant", "intro", language === "en" ? "Ready to read your values." : "Listo para leer tus valores.")];
      let currentCards = [cards.initial, cards.sibling];
      const edits: Record<string, unknown>[] = [];
      await page.route("**/api/v1/**", async (route) => {
        const request = route.request();
        const url = new URL(request.url());
        if (request.method() === "OPTIONS") return route.fulfill({ status: 204 });
        if (url.pathname === `/api/v1/conversations/${conversationId}/messages`) return json(route, { items: transcript, next_cursor: null });
        if (url.pathname.endsWith("/tool-results/artifact-call-one/recompute")) {
          const body = request.postDataJSON() as Record<string, unknown>;
          edits.push(body);
          expect(body.message_id).toBe("tool-message");
          const reset = edits.length === 2;
          expect(body.input_revision).toBe(reset ? 1 : 0);
          expect(body.arguments).toEqual(reset ? { known: 0 } : { known: 42, other: 7 });
          currentCards = [reset ? cards.zero : cards.edited, currentCards[1]];
          transcript[1] = message("assistant", "tool-message", "", { tool_result_cards: currentCards });
          return json(route, { message: transcript[1] });
        }
        if (url.pathname !== "/api/v1/chat/stream") return route.fallback();
        transcript = [message("user", "request-message", String(request.postDataJSON().message)), message("assistant", "tool-message", "", { tool_result_cards: currentCards })];
        const events = [{ type: "stage_start", stage: "interpret" }, { type: "final", payload: { message_id: "tool-message", stage_outcome: "execution_succeeded", final_response_payload: { tool_result_cards: currentCards } } }];
        return route.fulfill({ status: 200, contentType: "text/event-stream", body: events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join("") + "data: [DONE]\n\n" });
      });
      await page.goto(`/chat?conversation=${conversationId}`, { waitUntil: "networkidle" });
      await page.getByTestId("chat-input").fill(language === "en" ? "Read these values." : "Lee estos valores.");
      await page.getByTestId("chat-send").click();
      await expect(page.locator("[data-tool-result-card]")).toHaveCount(2);
      const card = page.locator('[data-tool-result-card]').first();
      await expect(card.locator("[data-tool-answer]")).toContainText("0");
      await card.locator("#artifact-call-one-known").fill("42");
      await card.locator("#artifact-call-one-other").fill("7");
      await expect(card).toHaveAttribute("data-input-revision", "1");
      await expect(card.locator("[data-tool-answer]")).toContainText("42");
      await expect(card.locator("#artifact-call-one-unknown")).toContainText((language === "en" ? en : es).tools.card.unknown);
      await card.locator("#artifact-call-one-known").fill("");
      await expect(card.getByRole("alert")).toBeVisible();
      await expect(card.locator("[data-previous-tool-result]")).toBeVisible();
      expect(edits).toHaveLength(1);
      await card.locator("#artifact-call-one-known").fill("0");
      await expect(card).toHaveAttribute("data-input-revision", "2");
      await page.reload({ waitUntil: "networkidle" });
      await expect(page.locator("[data-tool-result-card]")).toHaveCount(2);
      await expect(card.locator("#artifact-call-one-known")).toHaveValue("0");
      await expect(card.locator("#artifact-call-one-other")).toHaveValue("7");
      await expect(card.locator("[data-tool-answer]")).toContainText("0");
      await expect(page.locator("[data-tool-result-card]").nth(1).locator("[data-tool-answer]")).toContainText("40");
      expect(errors).toEqual([]);
      if (process.env.REGISTRY_SCREENSHOT_DIR) {
        mkdirSync(process.env.REGISTRY_SCREENSHOT_DIR, { recursive: true });
        await card.scrollIntoViewIfNeeded();
        await card.screenshot({ path: path.join(process.env.REGISTRY_SCREENSHOT_DIR, `tool-card-${language}-${width}.png`), animations: "disabled" });
      }
    });
  }
}

for (const language of ["en", "es-419"] as const) {
  test(`repeated asynchronous calls settle independently ${language}`, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await installMobileShellFixture(page, { language, theme: "light" });
    const toolJobs: ToolJob[] = [cards.initial, cards.sibling].map((card, index) => ({
      call_id: card.call_id, tool_name: card.tool_name, artifact_id: card.artifact_id,
      job: { id: `tool-job-${index}`, conversation_id: conversationId, request_message_id: "job-request", operation_scope: "chat.research", status: "queued", retryable: false },
    }));
    const source = message("assistant", "queued-tools", "", { tool_jobs: toolJobs });
    const transcript = [message("user", "job-request", language === "en" ? "Read both values." : "Lee ambos valores."), source];
    const finish: Array<() => void> = [];
    const gates = toolJobs.map((_, index) => new Promise<void>((resolve) => { finish[index] = resolve; }));
    await page.route("**/api/v1/**", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      if (request.method() === "OPTIONS") return route.fulfill({ status: 204 });
      if (url.pathname === `/api/v1/conversations/${conversationId}/messages`) return json(route, { items: transcript, next_cursor: null });
      const index = toolJobs.findIndex((call) => url.pathname === `/api/v1/backtest-jobs/${call.job.id}`);
      if (index === -1) return route.fallback();
      await gates[index];
      const card = index === 0 ? cards.initial : cards.sibling;
      const answer = message("assistant", `job-answer-${index}`, "", { tool_result_cards: [card] });
      toolJobs[index] = { ...toolJobs[index], job: { ...toolJobs[index].job, status: "succeeded" } };
      source.metadata = { tool_jobs: toolJobs };
      if (!transcript.some((entry) => entry.id === answer.id)) transcript.push(answer);
      return json(route, { job: toolJobs[index].job, run: null, result_message: answer });
    });
    await page.goto(`/chat?conversation=${conversationId}`, { waitUntil: "domcontentloaded" });
    await expect(page.locator("section.argus-card-reveal")).toHaveCount(2);
    await expect(page.locator("[data-tool-result-card]")).toHaveCount(0);
    finish[1]();
    await expect(page.locator("[data-tool-result-card]")).toHaveCount(1);
    await expect(page.locator("[data-tool-answer]")).toContainText("40");
    finish[0]();
    await expect(page.locator("[data-tool-result-card]")).toHaveCount(2);
    await page.reload({ waitUntil: "networkidle" });
    await expect(page.locator("[data-tool-result-card]")).toHaveCount(2);
    await expect(page.locator("[data-tool-answer]").first()).toContainText("40");
    await expect(page.locator("[data-tool-answer]").last()).toContainText("0");
    if (process.env.REGISTRY_SCREENSHOT_DIR) {
      mkdirSync(process.env.REGISTRY_SCREENSHOT_DIR, { recursive: true });
      await page.locator("[data-tool-result-card]").last().scrollIntoViewIfNeeded();
      await page.screenshot({ path: path.join(process.env.REGISTRY_SCREENSHOT_DIR, `tool-jobs-${language}.png`), animations: "disabled" });
    }
  });
}
