import { expect, test, type Page, type Route } from "@playwright/test";
import { mkdirSync } from "node:fs";

const NOW = "2026-08-02T12:00:00.000Z";
const EVIDENCE_DIR = process.env.ISSUE_334_EVIDENCE_DIR;

type FixtureState = {
  mutations: Array<{ conversationId: string; method: string; body?: unknown }>;
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function conversation(id: string, title: string) {
  return {
    id,
    title,
    title_source: "user_renamed",
    pinned: false,
    archived: false,
    deleted_at: null,
    created_at: NOW,
    updated_at: NOW,
    last_message_preview: `${title} summary`,
    language: "en",
  };
}

function searchItem(id: string, title: string) {
  return {
    type: "conversation",
    id,
    conversation_id: id,
    title,
    archived: false,
    matched_text: `${title} summary`,
    updated_at: NOW,
    match: { layer: "conversation", fragment: title, count: 1 },
    dossier: null,
    total_runs: 0,
    decided_runs: 0,
    decision_states: [],
  };
}

async function capture(page: Page, filename: string) {
  if (!EVIDENCE_DIR) return;
  mkdirSync(EVIDENCE_DIR, { recursive: true });
  await page.screenshot({ path: `${EVIDENCE_DIR}/${filename}`, fullPage: true });
}

async function installFixture(page: Page): Promise<FixtureState> {
  const state: FixtureState = { mutations: [] };
  const conversations = [
    conversation("legend-a", "Legend A"),
    conversation("legend-b", "Legend B"),
  ];

  await page.addInitScript(() => {
    window.localStorage.setItem("i18nextLng", "en");
    window.localStorage.setItem("argus:sidebar_mode", "expanded");
  });
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname.endsWith("/api/v1/me")) {
      return json(route, {
        user: {
          id: "issue-334-user",
          email: "issue-334@example.com",
          username: "issue334",
          display_name: "Issue 334",
          language: "en",
          locale: "en-US",
          onboarding: { completed: true, stage: "completed", language_confirmed: true, primary_goal: null },
        },
        account_kind: "registered",
        guest: null,
        capabilities: {
          can_create_additional_conversation: true,
          can_manage_conversation: true,
          can_save_decision: true,
          can_manage_account: true,
          can_use_omnisearch: true,
          can_search_current_workspace: true,
          can_use_grounded_discovery: true,
          can_submit_feedback: true,
        },
        public_account_access_enabled: false,
      });
    }
    if (url.pathname.endsWith("/api/v1/history")) {
      return json(route, {
        items: conversations.map((item) => ({
          type: "chat",
          id: item.id,
          conversation_id: item.id,
          title: item.title,
          subtitle: item.last_message_preview,
          pinned: false,
          created_at: NOW,
        })),
        next_cursor: null,
      });
    }
    if (url.pathname.endsWith("/api/v1/search")) {
      return json(route, {
        items: conversations.map((item) => searchItem(item.id, item.title)),
        next_cursor: null,
        ledger_groups: [],
      });
    }
    if (url.pathname.endsWith("/api/v1/conversations")) {
      return json(route, { items: conversations, next_cursor: null });
    }
    const match = url.pathname.match(/\/api\/v1\/conversations\/(legend-[ab])$/);
    if (match && (request.method() === "PATCH" || request.method() === "DELETE")) {
      state.mutations.push({
        conversationId: match[1],
        method: request.method(),
        body: request.method() === "PATCH" ? request.postDataJSON() : undefined,
      });
      return json(route, request.method() === "DELETE" ? { success: true } : { conversation: conversations.find((item) => item.id === match[1]) });
    }
    const messageMatch = url.pathname.match(/\/api\/v1\/conversations\/(legend-[ab])\/messages$/);
    if (messageMatch) {
      return json(route, {
        items: [{ id: `${messageMatch[1]}-message`, conversation_id: messageMatch[1], role: "assistant", content: "Ready.", created_at: NOW, metadata: {} }],
        next_cursor: null,
      });
    }
    if (url.pathname.endsWith("/activity")) {
      return json(route, { operation: { status: "idle", kind: null, updated_at: null }, attention: { status: "none", cursor: null } });
    }
    return json(route, { detail: `Unexpected ${request.method()} ${url.pathname}` }, 501);
  });
  return state;
}

async function openOmnisearch(page: Page) {
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page.getByPlaceholder("Search Argus...")).toBeVisible();
  await expect(page.locator('[data-palette-row-index="0"]')).toBeVisible();
}

test("keeps the legend quiet at rest, reveals it only on Ctrl hover, and executes every advertised action", async ({ page }) => {
  const fixture = await installFixture(page);
  await page.goto("/chat?conversation=legend-a");
  await openOmnisearch(page);

  const region = page.locator("[data-command-palette-action-region]");
  await region.hover();
  await expect(page.locator("[data-command-palette-shortcut-legend]")).toHaveCount(0);
  await capture(page, "01-hidden-at-rest.png");

  await page.keyboard.down("Control");
  await expect(page.locator("[data-command-palette-shortcut-legend]")).toContainText("Go");
  await expect(page.locator("[data-command-palette-shortcut-legend]")).toContainText("Rename");
  await expect(page.locator("[data-command-palette-shortcut-legend]")).toContainText("Archive");
  await expect(page.locator("[data-command-palette-shortcut-legend]")).toContainText("Delete");
  await capture(page, "02-revealed-on-ctrl-hover.png");
  await page.keyboard.up("Control");
  await expect(page.locator("[data-command-palette-shortcut-legend]")).toHaveCount(0);

  const firstRow = page.locator('[data-palette-row-index="0"]');
  await firstRow.focus();
  await firstRow.press("F2");
  await expect(page.getByRole("textbox", { name: "Rename conversation" })).toBeVisible();
  await page.keyboard.press("Escape");

  const secondRow = page.locator('[data-palette-row-index="1"]');
  await secondRow.focus();
  await secondRow.press("Shift+F2");
  await expect.poll(() => fixture.mutations).toContainEqual({
    conversationId: "legend-b",
    method: "PATCH",
    body: { archived: true },
  });

  const row = page.locator('[data-palette-row-index="0"]');
  await row.focus();
  await expect(page.locator("h2")).toHaveText("Legend A");
  await row.press("Delete");
  await expect(page.getByRole("alertdialog")).toContainText("Delete this conversation?");
  await page.getByRole("alertdialog").getByText("Cancel", { exact: true }).click();

  await row.press("Enter");
  await expect(page).toHaveURL(/conversation=legend-a(?:&|$)/);
  await openOmnisearch(page);
  await page.locator('[data-palette-row-index="1"]').focus();
  await expect(page.locator("h2")).toHaveText("Legend B");
  await page.keyboard.press("Control+Enter");
  await expect(page).toHaveURL(/conversation=legend-b(?:&|$)/);
});
