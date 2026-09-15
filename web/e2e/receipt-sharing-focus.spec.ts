import { expect, test } from "@playwright/test";
import { receiptCopy } from "../lib/receipt-copy";
import { installSharingFixture } from "./support/sharing-fixture";

// Run with the existing sharing flag explicitly enabled in the test server.
test.skip(process.env.NEXT_PUBLIC_EVIDENCE_RECEIPT_SHARING_ENABLED !== "true", "Sharing remains default off.");
for (const scenario of [
  { width: 390, language: "en", theme: "dark" },
  { width: 720, language: "en", theme: "dark" },
  { width: 1024, language: "en", theme: "dark" },
  { width: 1280, language: "en", theme: "dark" },
  { width: 390, language: "es-419", theme: "light" },
] as const) {
  test(`select and share in the conversation at ${scenario.width}px ${scenario.language} ${scenario.theme}`, async ({ page }, testInfo) => {
    const { width, language, theme } = scenario;
    const copy = receiptCopy(language);
    await page.setViewportSize({ width, height: 844 });
    const fixture = await installSharingFixture(page, language, theme);
    await page.goto(`/chat?conversation=${fixture.conversationId}`);
    await page.getByRole("button", { name: copy.selection.title, exact: true }).click();
    const transcript = page.getByTestId("conversation-transcript-region");
    await expect(transcript.getByRole("checkbox")).toHaveCount(2);
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(transcript.locator('[data-message-id="sharing-confirmation"]').getByRole("checkbox")).toHaveCount(0);
    await page.getByRole("button", { name: copy.selection.all, exact: true }).click();
    await expect(transcript.getByRole("checkbox").first()).toBeChecked();
    await expect(transcript.getByRole("checkbox").last()).toBeChecked();
    await page.screenshot({ path: testInfo.outputPath(`selection-${language}-${width}.png`) });
    await page.getByRole("button", { name: copy.selection.continue, exact: true }).click();
    const dialog = page.getByRole("dialog", { name: copy.selection.title, exact: true });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("checkbox")).toHaveCount(0);
    const note = language === "en" ? "My monthly experiment." : "Mi experimento mensual.";
    await dialog.getByLabel(copy.owner.note_label).fill(note);
    await dialog.getByRole("button", { name: copy.selection.preview, exact: true }).click();
    await expect(dialog.getByText(note)).toBeVisible();
    await expect(dialog.getByRole("heading", { name: language === "en" ? "What do the costs mean?" : "¿Qué significan los costos?" })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`preview-${language}-${width}.png`) });
    await dialog.getByRole("button", { name: copy.owner.create, exact: true }).click();
    await expect(dialog.getByRole("textbox", { name: copy.owner.copy, exact: true })).toHaveValue(/\/r\/sharing-fixture-public-link-604$/);
    expect(fixture.publications).toEqual([{ message_ids: ["sharing-answer-0", "sharing-answer-1"], owner_note: note, payload_digest: "seeded-preview-digest" }]);
    await page.screenshot({ path: testInfo.outputPath(`link-${language}-${width}.png`) });
  });
}
