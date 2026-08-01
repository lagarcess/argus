import { expect, test } from "@playwright/test";

const SCREENSHOT_DIR =
  "../docs/release-evidence/screenshots/issue-321";

type FakeTurnstileMode = "visible" | "stuck";

declare global {
  interface Window {
    rejectCaptchaForTest?: () => void;
  }
}

async function prepareCaptcha(
  page: import("@playwright/test").Page,
  language: "en" | "es-419",
  mode: FakeTurnstileMode,
) {
  await page.addInitScript(
    ({ language: selectedLanguage, mode: selectedMode }) => {
      window.localStorage.setItem("i18nextLng", selectedLanguage);
      window.localStorage.setItem("argus-theme", "dark");
      Object.defineProperty(window, "turnstile", {
        configurable: true,
        value: {
          render(
            container: HTMLElement,
            options: {
              theme?: "auto" | "light" | "dark";
              "before-interactive-callback"?: () => void;
              "error-callback"?: () => boolean;
            },
          ) {
            document.documentElement.dataset.renderedTurnstileTheme =
              options.theme;
            window.rejectCaptchaForTest = () => {
              options["error-callback"]?.();
            };
            if (selectedMode === "visible") {
              const frame = document.createElement("iframe");
              frame.title = "Turnstile test challenge";
              frame.style.width = "300px";
              frame.style.height = "65px";
              frame.style.border = "0";
              frame.srcdoc =
                options.theme === "dark"
                  ? "<!doctype html><html><body style='margin:0;background:#222;color:#f5f5f5;font:15px system-ui;display:flex;align-items:center;height:65px'><div style='width:22px;height:22px;border:2px solid #aaa;margin:0 12px 0 16px'></div><strong>Verify you are human</strong></body></html>"
                  : "<!doctype html><html><body style='margin:0;background:#fff;color:#171717;font:15px system-ui;display:flex;align-items:center;height:65px'><div style='width:22px;height:22px;border:2px solid #666;margin:0 12px 0 16px'></div><strong>Verify you are human</strong></body></html>";
              container.appendChild(frame);
              options["before-interactive-callback"]?.();
            }
            return "issue-321-test-widget";
          },
          remove() {},
        },
      });
    },
    { language, mode },
  );
}

async function submitLogin(page: import("@playwright/test").Page) {
  await page.goto("/?auth=login");
  await page.locator('input[type="email"]').fill("captcha-probe@example.com");
  await page.locator('input[type="password"]').fill("not-a-real-password");
  await page.locator('button[type="submit"]').click();
}

for (const fixture of [
  {
    language: "en" as const,
    label: "Verifying you’re not a bot…",
    screenshot: "forced-visible-challenge-en.png",
  },
  {
    language: "es-419" as const,
    label: "Verificando que no eres un bot…",
    screenshot: "forced-visible-challenge-es-419.png",
  },
]) {
  test(`forced interactive challenge has a ${fixture.language} visual shell`, async ({
    page,
  }) => {
    await prepareCaptcha(page, fixture.language, "visible");
    await submitLogin(page);

    const shell = page.getByTestId("turnstile-challenge-shell");
    await expect(shell).toBeVisible();
    await expect(shell).toHaveAttribute("role", "dialog");
    await expect(shell.getByRole("heading", { name: fixture.label })).toBeVisible();
    await expect(shell.getByTitle("Turnstile test challenge")).toBeVisible();
    await expect(shell).toBeFocused();
    await expect(page.locator("html")).toHaveAttribute(
      "data-rendered-turnstile-theme",
      "dark",
    );

    await page.locator('input[type="email"]').evaluate((input) => {
      (input as HTMLInputElement).focus();
    });
    await expect(shell).toBeFocused();

    await page.waitForTimeout(250);
    await page.screenshot({
      path: `${SCREENSHOT_DIR}/${fixture.screenshot}`,
      fullPage: true,
    });

    await page.evaluate(() => window.rejectCaptchaForTest?.());
    await expect(shell).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: /Sign in|Iniciar sesión/ }),
    ).toBeFocused();
  });
}

test("a stuck shared CAPTCHA times out and leaves login ready to retry", async ({
  page,
}) => {
  test.setTimeout(25_000);
  await prepareCaptcha(page, "en", "stuck");
  await submitLogin(page);

  await expect(page.getByTestId("auth-submit-spinner")).toBeVisible();
  await expect(
    page.getByText("We couldn’t complete the security check. Please try again."),
  ).toBeVisible({ timeout: 18_000 });
  await expect(page.getByPlaceholder("Email address")).toHaveValue(
    "captcha-probe@example.com",
  );
  await expect(page.getByPlaceholder("Password")).toHaveValue(
    "not-a-real-password",
  );
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeEnabled();
  await expect(page.getByTestId("turnstile-challenge-shell")).toHaveCount(0);
});
