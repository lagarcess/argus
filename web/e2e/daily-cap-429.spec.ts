import { expect, test } from "@playwright/test";
import {
  COPY,
  MIDNIGHT_RETRY_AFTER,
  RAW_SERVER_DETAIL,
  VIEWPORTS,
  captureEvidence,
  installComputeLimitJourney,
  sendQuestion,
} from "./fixtures/compute-limit-journey";

test.use({ timezoneId: "America/Santo_Domingo" });

for (const language of ["en", "es-419"] as const) {
  for (const viewport of VIEWPORTS) {
    for (const account of ["guest", "registered"] as const) {
      for (const header of ["midnight", "missing"] as const) {
        test(`daily cap states the local reset: ${account}, ${language}, ${viewport.name}, ${header} header`, async ({ page }) => {
          await page.setViewportSize(viewport);
          const evidence = await installComputeLimitJourney(page, {
            account, language, status: 429,
            retryAfter: header === "midnight" ? MIDNIGHT_RETRY_AFTER : undefined,
          });
          await sendQuestion(page, language);
          const copy = COPY[language];
          await expect(page.getByText(copy.capError, { exact: true })).toBeVisible();
          await expect(page.getByText(copy.prompt, { exact: true })).toHaveCount(1);
          await expect(page.getByText(RAW_SERVER_DETAIL, { exact: true })).toHaveCount(0);
          await expect(page.getByText(/wait a moment|espera un momento/i)).toHaveCount(0);
          await expect(page.getByRole("button", { name: copy.retrySoon })).toHaveCount(0);
          expect(evidence.streamStatuses).toEqual([429]);
          if (header === "midnight") {
            await captureEvidence(page, `${account}-429-${language}-${viewport.name}`);
          }
        });
      }
    }
  }
}

test("a new chat keeps the rejected question and its daily reset notice", async ({ page }) => {
  const evidence = await installComputeLimitJourney(page, {
    account: "registered", language: "en", status: 429,
    retryAfter: MIDNIGHT_RETRY_AFTER, newConversation: true,
  });
  await sendQuestion(page, "en", true);
  await expect(page.getByText(COPY.en.capError, { exact: true })).toBeVisible();
  await expect(page.getByText(COPY.en.prompt, { exact: true })).toHaveCount(1);
  expect(evidence.streamStatuses).toEqual([429]);
});
