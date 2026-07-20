import { expect, test, type Locator, type Page } from "@playwright/test";

const EVIDENCE_DIR = "../temp/qa-evidence-250/e2e";

type NetworkWatch = {
  featureRequests: string[];
  pageErrors: string[];
  start: () => void;
};

// Range interactions must be presentation-only: no API, provider, simulation,
// usage, or durable-write request may fire once interaction starts. Next.js
// dev-server assets and the HMR websocket live under /_next and are excluded.
function watchFeatureNetwork(page: Page): NetworkWatch {
  const featureRequests: string[] = [];
  const pageErrors: string[] = [];
  let started = false;
  page.on("pageerror", (error) => {
    pageErrors.push(String(error));
  });
  page.on("request", (request) => {
    if (!started) return;
    const url = new URL(request.url());
    const sameHost = url.host === new URL(page.url()).host;
    const isNextAsset = url.pathname.startsWith("/_next");
    const isStaticAsset =
      url.pathname.startsWith("/locales/") || url.pathname === "/favicon.ico";
    const isApiShaped = url.pathname.includes("/api/");
    const isWebSocket = request.resourceType() === "websocket";
    if (
      isApiShaped ||
      (!sameHost && !isNextAsset) ||
      (isWebSocket && !isNextAsset) ||
      (sameHost && !isNextAsset && !isStaticAsset && url.pathname !== "/dev/result-card")
    ) {
      featureRequests.push(`${request.method()} ${url.host}${url.pathname}`);
    }
  });
  return {
    featureRequests,
    pageErrors,
    start: () => {
      started = true;
    },
  };
}

async function openPlayground(page: Page) {
  await page.goto("/dev/result-card", { waitUntil: "networkidle" });
  await expect(
    page.getByTestId("result-card-fixture-adaptive-intraday-result").first(),
  ).toBeVisible();
}

function adaptiveCard(page: Page) {
  return page.getByTestId("result-card-fixture-adaptive-intraday-result").first();
}

async function fullRunTexts(card: Locator) {
  const metric = await card
    .getByText("+$120 gain · +12.0% total return", { exact: true })
    .textContent();
  const period = await card
    .getByText("Jan 1, 2026 → Jan 15, 2026 · Hourly data", { exact: true })
    .textContent();
  return { metric, period };
}

async function openRangeDetails(card: Locator) {
  await card.getByTestId("result-chart-details-toggle").click();
  await expect(card.getByTestId("result-chart-visible-period")).toBeVisible();
}

test("adaptive hourly result switches presets, custom range, pan, and reset without network", async ({
  page,
}) => {
  const watch = watchFeatureNetwork(page);
  await openPlayground(page);
  const card = adaptiveCard(page);
  await card.scrollIntoViewIfNeeded();
  await expect(card.getByTestId("result-chart-range-ALL")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  // Quiet by default: no telemetry above the result, facts live in details.
  await expect(card.getByTestId("result-chart-visible-period")).toHaveCount(0);
  await expect(card.getByTestId("result-chart-details-toggle")).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  // Eligible presets render in the conventional sequence.
  const order = await card
    .locator('[data-testid^="result-chart-range-"]')
    .evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("data-testid")),
    );
  expect(order).toEqual([
    "result-chart-range-1D",
    "result-chart-range-1W",
    "result-chart-range-ALL",
  ]);
  // Slim visible control, real 44px interactive target.
  const buttonHeight = await card
    .getByTestId("result-chart-range-ALL")
    .evaluate((node) => node.getBoundingClientRect().height);
  expect(buttonHeight).toBeGreaterThanOrEqual(44);
  const before = await fullRunTexts(card);
  await card.screenshot({ path: `${EVIDENCE_DIR}/e2e-01-adaptive-all.png` });

  watch.start();

  await card.getByTestId("result-chart-range-1D").click();
  await expect(card.getByTestId("result-chart-range-1D")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(await fullRunTexts(card)).toEqual(before);
  await openRangeDetails(card);
  await expect(card.getByTestId("result-chart-visible-period")).toContainText(
    "2026",
  );
  await card.screenshot({ path: `${EVIDENCE_DIR}/e2e-02-adaptive-1d.png` });

  // Custom lives inside the open disclosure; a valid apply closes it.
  await card.getByTestId("result-chart-custom-start").fill("2026-01-05");
  await card.getByTestId("result-chart-custom-end").fill("2026-01-08");
  await card.getByTestId("result-chart-custom-apply").click();
  await expect(card.getByTestId("result-chart-custom-indicator")).toBeVisible();
  await expect(card.getByTestId("result-chart-visible-period")).toHaveCount(0);
  await expect(card.getByTestId("result-chart-details-toggle")).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  await openRangeDetails(card);
  await expect(card.getByTestId("result-chart-visible-period")).toContainText(
    "Jan 5, 2026",
  );
  expect(await fullRunTexts(card)).toEqual(before);

  await card.getByTestId("result-chart-reset").click();
  await expect(card.getByTestId("result-chart-range-ALL")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(card.getByTestId("result-chart-custom-indicator")).toHaveCount(0);
  expect(await fullRunTexts(card)).toEqual(before);

  // Manual pan flips the selection to Custom without touching run truth. Raw
  // mouse events do not auto-scroll, so bring the canvas itself into view.
  const canvas = card.getByTestId("result-equity-chart");
  await canvas.scrollIntoViewIfNeeded();
  const chartBox = await canvas.boundingBox();
  expect(chartBox).not.toBeNull();
  if (chartBox) {
    const centerY = chartBox.y + chartBox.height / 2;
    await page.mouse.move(chartBox.x + chartBox.width * 0.6, centerY);
    await page.mouse.down();
    await page.mouse.move(chartBox.x + chartBox.width * 0.25, centerY, {
      steps: 8,
    });
    await page.mouse.up();
  }
  await expect(card.getByTestId("result-chart-custom-indicator")).toBeVisible();
  expect(await fullRunTexts(card)).toEqual(before);

  await card.getByTestId("result-chart-reset").click();
  await expect(card.getByTestId("result-chart-range-ALL")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(await fullRunTexts(card)).toEqual(before);
  expect(watch.featureRequests).toEqual([]);
  expect(watch.pageErrors).toEqual([]);
});

test("monthly recurring result suppresses sub-cycle presets and keeps metrics", async ({
  page,
}) => {
  const watch = watchFeatureNetwork(page);
  await openPlayground(page);
  const card = page.getByTestId("result-card-fixture-dca-result").first();
  await card.scrollIntoViewIfNeeded();

  await expect(card.getByTestId("result-chart-range-3M")).toBeVisible();
  await expect(card.getByTestId("result-chart-range-ALL")).toBeVisible();
  await expect(card.getByTestId("result-chart-range-1D")).toHaveCount(0);
  await expect(card.getByTestId("result-chart-range-1W")).toHaveCount(0);
  await expect(card.getByTestId("result-chart-range-1M")).toHaveCount(0);
  const order = await card
    .locator('[data-testid^="result-chart-range-"]')
    .evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("data-testid")),
    );
  expect(order).toEqual([
    "result-chart-range-3M",
    "result-chart-range-YTD",
    "result-chart-range-1Y",
    "result-chart-range-ALL",
  ]);

  const metric = card.getByText("$0 change · 0.0% total return", {
    exact: true,
  });
  const period = card.getByText(
    "January 3, 2022 to December 29, 2023 · Daily data",
    { exact: true },
  );
  await expect(metric).toBeVisible();
  await expect(period).toBeVisible();

  watch.start();
  await card.getByTestId("result-chart-range-3M").click();
  await expect(card.getByTestId("result-chart-range-3M")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await openRangeDetails(card);
  await expect(card.getByTestId("result-chart-visible-period")).toContainText(
    "2023",
  );
  // Daily results present dates only — no session-time artifacts.
  await expect(card.getByTestId("result-chart-visible-period")).not.toContainText(
    /\d:\d{2}/,
  );
  await expect(card.getByTestId("result-chart-peak")).not.toContainText(
    /\d:\d{2}/,
  );
  await expect(metric).toBeVisible();
  await expect(period).toBeVisible();
  await card.screenshot({ path: `${EVIDENCE_DIR}/e2e-03-dca-3m.png` });
  expect(watch.featureRequests).toEqual([]);
  expect(watch.pageErrors).toEqual([]);
});

test("legacy persisted payload renders observation-qualified controls without optional objects", async ({
  page,
}) => {
  const watch = watchFeatureNetwork(page);
  await openPlayground(page);
  const card = page
    .getByTestId("result-card-fixture-old-persisted-card-shape")
    .first();
  await card.scrollIntoViewIfNeeded();

  // Eight sparse points qualify no shorter preset; ALL and details remain.
  await expect(card.getByTestId("result-chart-range-ALL")).toBeVisible();
  for (const key of ["1D", "1W", "1M", "3M", "YTD", "1Y"]) {
    await expect(card.getByTestId(`result-chart-range-${key}`)).toHaveCount(0);
  }
  watch.start();
  await openRangeDetails(card);
  // Without marker_summary the card must not claim sampling or completeness.
  await expect(card.getByTestId("result-chart-marker-cap")).toHaveCount(0);
  await expect(card.getByTestId("result-chart-event-sampling")).toHaveCount(0);
  await expect(card.getByTestId("result-chart-event-count")).toContainText(
    "No displayed executed-fill events",
  );

  await card.getByTestId("result-chart-custom-start").fill("2022-01-01");
  await card.getByTestId("result-chart-custom-end").fill("2024-01-01");
  await card.getByTestId("result-chart-custom-apply").click();
  await expect(card.getByTestId("result-chart-custom-indicator")).toBeVisible();
  await card.getByTestId("result-chart-reset").click();
  await expect(card.getByTestId("result-chart-range-ALL")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(card.getByTestId("result-chart-reset")).toHaveCount(0);
  expect(watch.featureRequests).toEqual([]);
  expect(watch.pageErrors).toEqual([]);
});

test("visible evidence tracks the viewport with separate sampling disclosures", async ({
  page,
}) => {
  const watch = watchFeatureNetwork(page);
  await openPlayground(page);
  const card = adaptiveCard(page);
  await card.scrollIntoViewIfNeeded();
  await openRangeDetails(card);

  const allPeriod = await card
    .getByTestId("result-chart-visible-period")
    .textContent();
  const allLow = await card.getByTestId("result-chart-low").textContent();
  // Hourly observations keep meaningful time information.
  expect(allPeriod).toContain("12:00");
  await expect(card.getByTestId("result-chart-event-row")).toHaveCount(20);
  const firstRow = card.getByTestId("result-chart-event-row").first();
  const lastRow = card.getByTestId("result-chart-event-row").last();
  await expect(firstRow).toContainText("Buy AAPL");
  await expect(firstRow).toContainText("Jan 1, 2026");
  await expect(lastRow).toContainText("Sell AAPL");
  await expect(lastRow).toContainText("Jan 15, 2026");
  await expect(card.getByTestId("result-chart-event-sampling")).toContainText(
    "Showing 20 of 80 supplied events.",
  );
  await expect(card.getByTestId("result-chart-marker-cap")).toContainText(
    "Argus stored 80 of 124 executed-fill groups for this result.",
  );
  await card.screenshot({
    path: `${EVIDENCE_DIR}/e2e-04-sampled-disclosure.png`,
  });

  watch.start();
  await card.getByTestId("result-chart-range-1D").click();
  await expect(card.getByTestId("result-chart-range-1D")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(card.getByTestId("result-chart-visible-period")).not.toHaveText(
    allPeriod ?? "",
  );
  // This fixture rises into its final observation, so the 1D peak legitimately
  // stays the run peak; the low must move to the visible window's floor.
  await expect(card.getByTestId("result-chart-peak")).toContainText("$1,120");
  await expect(card.getByTestId("result-chart-low")).not.toHaveText(
    allLow ?? "",
  );
  await expect(card.getByTestId("result-chart-event-count")).toContainText(
    "6 displayed executed-fill events in this range.",
  );
  await expect(card.getByTestId("result-chart-event-row")).toHaveCount(6);
  // The frontend list is complete for this window; only the backend cap remains.
  await expect(card.getByTestId("result-chart-event-sampling")).toHaveCount(0);
  await expect(card.getByTestId("result-chart-marker-cap")).toContainText(
    "80 of 124",
  );
  expect(watch.featureRequests).toEqual([]);
  expect(watch.pageErrors).toEqual([]);
});

test("Spanish mobile keyboard journey keeps localized accessible controls", async ({
  page,
}) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("i18nextLng", "es-419");
  });
  await page.setViewportSize({ width: 390, height: 844 });
  const watch = watchFeatureNetwork(page);
  await openPlayground(page);
  await expect(page.locator("html")).toHaveAttribute("lang", "es-419");

  const card = adaptiveCard(page);
  await card.scrollIntoViewIfNeeded();
  await expect(card.getByTestId("result-chart-range-1W")).toHaveText("1S");
  await expect(card.getByTestId("result-chart-range-ALL")).toHaveText("Todo");
  await expect(card.getByTestId("result-chart-details-toggle")).toContainText(
    "Detalles del rango",
  );

  watch.start();
  await card.getByTestId("result-chart-range-1D").focus();
  await page.keyboard.press("Tab");
  await expect(card.getByTestId("result-chart-range-1W")).toBeFocused();
  const focusRing = await card
    .getByTestId("result-chart-range-1W")
    .evaluate((element) => getComputedStyle(element).boxShadow);
  expect(focusRing).not.toBe("none");
  const pillHeight = await card
    .getByTestId("result-chart-range-1W")
    .evaluate((element) => element.getBoundingClientRect().height);
  expect(pillHeight).toBeGreaterThanOrEqual(44);

  await page.keyboard.press("Tab");
  await expect(card.getByTestId("result-chart-range-ALL")).toBeFocused();
  await openRangeDetails(card);
  await expect(card.getByText("Rango personalizado")).toBeVisible();

  await card.getByTestId("result-chart-custom-start").fill("2026-01-08");
  await card.getByTestId("result-chart-custom-end").fill("2026-01-05");
  await card.getByTestId("result-chart-custom-apply").click();
  await expect(card.getByTestId("result-chart-custom-error")).toHaveText(
    "La fecha de inicio debe ser anterior a la fecha de fin.",
  );
  // Invalid input keeps the disclosure open with entered values preserved.
  await expect(card.getByTestId("result-chart-custom-start")).toHaveValue(
    "2026-01-08",
  );

  await card.getByTestId("result-chart-custom-start").fill("2026-01-05");
  await card.getByTestId("result-chart-custom-end").fill("2026-01-08");
  await card.getByTestId("result-chart-custom-apply").click();
  await expect(card.getByTestId("result-chart-custom-indicator")).toBeVisible();
  await expect(card.getByTestId("result-chart-custom-indicator")).toContainText(
    "Personalizado",
  );
  await expect(card.getByTestId("result-chart-reset")).toHaveText(
    "Restablecer",
  );
  await openRangeDetails(card);
  await expect(card.getByTestId("result-chart-visible-period")).toContainText(
    "ene",
  );
  await card.screenshot({ path: `${EVIDENCE_DIR}/e2e-05-spanish-mobile.png` });
  expect(watch.featureRequests).toEqual([]);
  expect(watch.pageErrors).toEqual([]);
});
