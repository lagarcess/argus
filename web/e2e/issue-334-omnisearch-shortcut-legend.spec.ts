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
      if (request.method() === "PATCH") {
        const body = request.postDataJSON();
        const conversationId = url.pathname.split("/").at(-2) ?? "";
        state.mutations.push({ conversationId, method: "PATCH_ACTIVITY", body });
        return json(route, {
          operation: { status: "idle", kind: null, updated_at: null },
          attention: {
            status: body.action === "mark_unread" ? "manual_unread" : "none",
            cursor: null,
          },
        });
      }
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

async function primaryModifier(page: Page) {
  return page.evaluate(() =>
    /Mac|iPhone|iPad|iPod/.test(navigator.userAgent) ? "Meta" : "Control",
  );
}

test("keeps the legend quiet at rest, reveals it on primary-modifier hover, and executes every advertised action", async ({ page }) => {
  const fixture = await installFixture(page);
  await page.goto("/chat?conversation=legend-a");
  await openOmnisearch(page);
  const modifier = await primaryModifier(page);

  const region = page.locator("[data-command-palette-action-region]");
  await region.hover();
  await expect(page.locator("[data-command-palette-shortcut-legend]")).toHaveCount(0);
  await capture(page, "01-hidden-at-rest.png");

  await page.keyboard.down(modifier);
  const legend = page.locator("[data-command-palette-shortcut-legend]");
  await expect(legend).toContainText("Go");
  await expect(legend).toContainText("Rename");
  await expect(legend).toContainText("Archive");
  await expect(legend).toContainText("Delete");
  await expect(legend).toContainText(
    modifier === "Meta" ? "⌘⇧R" : "Ctrl⇧R",
  );
  await expect(legend).toContainText(
    modifier === "Meta" ? "⌘⇧A" : "Ctrl⇧A",
  );
  await expect(legend).toContainText(
    modifier === "Meta" ? "⌘⇧D" : "Ctrl⇧D",
  );
  await expect(legend).not.toContainText("Continue");
  await capture(page, "02-revealed-on-ctrl-hover.png");
  await page.keyboard.up(modifier);
  await expect(page.locator("[data-command-palette-shortcut-legend]")).toHaveCount(0);

  const search = page.getByPlaceholder("Search Argus...");
  await search.press(
    modifier === "Meta" ? "Meta+Alt+Digit2" : "Control+Shift+Digit2",
  );
  const secondRow = page.locator('[data-palette-row-index="1"]');
  await expect(secondRow).toBeFocused();

  await secondRow.press(`${modifier}+Shift+KeyR`);
  await expect(page.getByRole("textbox", { name: "Rename conversation" })).toBeVisible();
  await page.keyboard.press("Escape");

  await secondRow.focus();
  await secondRow.press(`${modifier}+Shift+KeyA`);
  await expect.poll(() => fixture.mutations).toContainEqual({
    conversationId: "legend-b",
    method: "PATCH",
    body: { archived: true },
  });

  const row = page.locator('[data-palette-row-index="0"]');
  await row.focus();
  await expect(page.locator("h2")).toHaveText("Legend A");

  await row.getByRole("button", { name: "Delete conversation" }).click();
  const pointerDialog = page.getByRole("alertdialog");
  await expect(pointerDialog).toContainText("Delete this conversation?");
  await expect(pointerDialog).not.toContainText("Esc");
  await expect(pointerDialog).not.toContainText("↵");
  await capture(page, "05-pointer-delete-confirmation.png");
  await pointerDialog.getByRole("button", { name: "Cancel" }).click();

  await row.focus();
  await row.press(`${modifier}+Shift+KeyD`);
  await expect(page.getByRole("alertdialog")).toContainText("Delete this conversation?");
  await expect(page.getByRole("alertdialog")).toContainText("Esc");
  await expect(page.getByRole("alertdialog")).toContainText("↵");
  await capture(page, "05-delete-confirmation.png");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("alertdialog")).toHaveCount(0);

  await row.press(`${modifier}+Shift+KeyD`);
  await page.keyboard.press("Enter");
  await expect.poll(() => fixture.mutations).toContainEqual({
    conversationId: "legend-a",
    method: "DELETE",
  });

  await expect(page.getByRole("alertdialog")).toHaveCount(0);
  await page.keyboard.press("Escape");
  await openOmnisearch(page);
  await page.locator('[data-palette-row-index="1"]').focus();
  await expect(page.locator("h2")).toHaveText("Legend B");
  await page.keyboard.press(`${modifier}+Enter`);
  await expect(page).toHaveURL(/conversation=legend-b(?:&|$)/);
});

test("keeps background sidebar shortcut hints hidden while Omnisearch owns focus", async ({ page }) => {
  await installFixture(page);
  await page.goto("/chat?conversation=legend-a");
  const modifier = await primaryModifier(page);

  await openOmnisearch(page);
  await page.keyboard.down(modifier);

  const sidebar = page.locator("aside");
  await expect(sidebar).not.toContainText(
    modifier === "Meta" ? "⌘K" : "Ctrl+K",
  );
  await page.keyboard.up(modifier);
});

test("renders the OS-aware shortcut contract consistently in Help", async ({ page }) => {
  await installFixture(page);
  await page.goto("/chat?conversation=legend-a");
  const modifier = await primaryModifier(page);
  const composer = page.getByRole("combobox");
  await expect(composer).toBeVisible();

  await composer.press(`${modifier}+/`);
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("Rename current chat");
  await expect(dialog).toContainText("Archive current chat");
  await expect(dialog).toContainText("Delete current chat");
  await expect(dialog).toContainText("Mark current chat as read or unread");
  const platformShift = dialog.locator("kbd").filter({
    hasText: modifier === "Meta" ? "⇧" : "Shift",
  });
  expect(await platformShift.count()).toBeGreaterThan(0);
  if (modifier === "Meta") {
    await expect(dialog.locator("kbd").filter({ hasText: "Shift" })).toHaveCount(0);
  }
  await capture(page, "07-keyboard-shortcuts-consistent.png");
});

test("uses the same management bindings on the active chat", async ({ page }) => {
  const fixture = await installFixture(page);
  await page.goto("/chat?conversation=legend-a");
  const modifier = await primaryModifier(page);
  const composer = page.getByRole("combobox");
  await expect(composer).toBeVisible();
  await page.evaluate(() => {
    document.documentElement.dataset.argusCapturedShortcuts = "";
    document.addEventListener(
      "keydown",
      (event) => {
        if (
          ["KeyR", "KeyD", "KeyU", "KeyA"].includes(event.code) &&
          (event.metaKey || event.ctrlKey) &&
          event.shiftKey
        ) {
          const captured =
            document.documentElement.dataset.argusCapturedShortcuts;
          document.documentElement.dataset.argusCapturedShortcuts = [
            captured,
            `${event.code}:${event.defaultPrevented}`,
          ]
            .filter(Boolean)
            .join(",");
        }
      },
      true,
    );
  });

  await composer.press(`${modifier}+Shift+KeyR`);
  await expect(page.getByRole("textbox")).toBeVisible();
  await page.keyboard.press("Escape");

  await page.keyboard.press(`${modifier}+Shift+KeyD`);
  await expect(page.getByRole("alertdialog")).toContainText(
    "Delete this conversation?",
  );
  await expect(page.getByRole("alertdialog")).toContainText("Esc");
  await expect(page.getByRole("alertdialog")).toContainText("↵");
  await page.keyboard.press("Escape");

  await page.keyboard.press(`${modifier}+Shift+KeyU`);
  await expect.poll(() => fixture.mutations).toContainEqual({
    conversationId: "legend-a",
    method: "PATCH_ACTIVITY",
    body: { action: "mark_unread" },
  });

  await page.keyboard.press(`${modifier}+Shift+KeyA`);
  await expect.poll(() => fixture.mutations).toContainEqual({
    conversationId: "legend-a",
    method: "PATCH",
    body: { archived: true },
  });
  await expect(page.locator("html")).toHaveAttribute(
    "data-argus-captured-shortcuts",
    "KeyR:true,KeyD:true,KeyU:true,KeyA:true",
  );
});

test("keeps Collapse at the far edge while the shortcut legend is hidden", async ({ page }) => {
  await installFixture(page);
  await page.goto("/chat?conversation=legend-a");
  await openOmnisearch(page);

  const collapse = page.getByRole("button", {
    name: "Collapse",
    exact: true,
  });
  await expect(collapse).toBeVisible();
  await capture(page, "03-collapse-at-right.png");
  const rightOffset = await collapse.evaluate(
    (element) => {
      const footer = element.parentElement?.parentElement;
      if (!footer) {
        throw new Error("Command palette footer was not found");
      }

      return footer.getBoundingClientRect().right - element.getBoundingClientRect().right;
    },
  );

  expect(rightOffset).toBeLessThanOrEqual(16);
});

test("uses arrow keys to move between the search field and visible rows", async ({ page }) => {
  await installFixture(page);
  await page.goto("/chat?conversation=legend-a");
  await openOmnisearch(page);

  const search = page.getByPlaceholder("Search Argus...");
  const firstRow = page.locator('[data-palette-row-index="0"]');
  const secondRow = page.locator('[data-palette-row-index="1"]');

  await expect(search).toBeFocused();
  await search.press("ArrowDown");
  await expect(firstRow).toBeFocused();
  await expect(page.locator("h2")).toHaveText("Legend A");
  const focusTreatment = await firstRow.evaluate((element) => {
    const style = window.getComputedStyle(element);
    return {
      boxShadow: style.boxShadow,
      outlineStyle: style.outlineStyle,
    };
  });
  expect(focusTreatment.outlineStyle).toBe("none");
  expect(focusTreatment.boxShadow).not.toBe("none");
  await capture(page, "06-neutral-keyboard-focus.png");

  await firstRow.press("ArrowDown");
  await expect(secondRow).toBeFocused();
  await expect(page.locator("h2")).toHaveText("Legend B");

  await secondRow.press("ArrowUp");
  await expect(firstRow).toBeFocused();
  await firstRow.press("ArrowUp");
  await expect(search).toBeFocused();
});

test("replaces the count with the shortcut legend in collapsed mode", async ({ page }) => {
  await installFixture(page);
  await page.goto("/chat?conversation=legend-a");
  await openOmnisearch(page);

  await page
    .getByRole("button", { name: "Collapse", exact: true })
    .click();
  const expand = page.getByRole("button", { name: "Expand", exact: true });
  await expect(expand).toBeVisible();
  await expect(page.getByText("2 conversations", { exact: true })).toBeVisible();

  await page.locator("[data-command-palette-action-region]").hover();
  const modifier = await primaryModifier(page);
  await page.keyboard.down(modifier);

  const legend = page.locator("[data-command-palette-shortcut-legend]");
  await expect(legend).toBeVisible();
  await expect(page.getByText("2 conversations", { exact: true })).toHaveCount(0);
  const spacing = await legend.evaluate((element) => {
    const expandButton = element.parentElement?.querySelector("button");
    if (!expandButton) {
      throw new Error("Expand button was not found beside the shortcut legend");
    }

    const legendRect = element.getBoundingClientRect();
    const expandRect = expandButton.getBoundingClientRect();
    const actionRects = Array.from(
      element.querySelectorAll("[data-command-palette-shortcut-action]"),
      (action) => action.getBoundingClientRect(),
    );
    return {
      horizontalGap: expandRect.left - legendRect.right,
      contentOverflow:
        Math.max(...actionRects.map((rect) => rect.right)) - legendRect.right,
      verticalCenterDelta: Math.abs(
        legendRect.top + legendRect.height / 2 -
          (expandRect.top + expandRect.height / 2),
      ),
    };
  });
  expect(spacing.horizontalGap).toBeGreaterThanOrEqual(8);
  expect(spacing.contentOverflow).toBeLessThanOrEqual(0.5);
  expect(spacing.verticalCenterDelta).toBeLessThanOrEqual(2);
  await capture(page, "04-collapsed-revealed.png");

  await page.keyboard.up(modifier);
  await expect(legend).toHaveCount(0);
  await expect(page.getByText("2 conversations", { exact: true })).toBeVisible();
});
