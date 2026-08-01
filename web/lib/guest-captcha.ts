export type GuestCaptchaPlan =
  | { kind: "token"; token: string }
  | { kind: "turnstile"; siteKey: string }
  | { kind: "unavailable" };

type TurnstileApi = {
  render(
    container: HTMLElement,
    options: {
      sitekey: string;
      appearance: "interaction-only";
      theme: "light" | "dark";
      callback: (token: string) => void;
      "error-callback": () => boolean;
      "expired-callback": () => void;
      "before-interactive-callback": () => void;
    },
  ): string;
  remove(widgetId: string): void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const TURNSTILE_SCRIPT_ID = "argus-guest-turnstile-script";
const TURNSTILE_SCRIPT_URL =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
export const CAPTCHA_ACQUISITION_TIMEOUT_MS = 15_000;
export const CAPTCHA_INTERACTIVE_TIMEOUT_MS = 300_000;
let turnstileScriptPromise: Promise<TurnstileApi> | null = null;
let captchaShellSequence = 0;

type CaptchaUnavailableError = Error & { code: "captcha_unavailable" };

type TurnstileShell = {
  container: HTMLElement;
  reveal(): void;
  destroy(): void;
};

function captchaUnavailableError(): CaptchaUnavailableError {
  const error = new Error(
    "Browser CAPTCHA could not be verified.",
  ) as CaptchaUnavailableError;
  error.code = "captcha_unavailable";
  return error;
}

export function guestCaptchaTokenForEnvironment(input: {
  nodeEnv: string | undefined;
  apiUrl: string | undefined;
  localQaToken: string | undefined;
  browserCaptchaToken?: string | null;
}): string | null {
  const browserToken = input.browserCaptchaToken?.trim() ?? "";
  if (browserToken) return browserToken;
  if (input.nodeEnv !== "production") {
    return "argus-local-browser-qa";
  }
  const token = input.localQaToken?.trim() ?? "";
  if (!token) return null;
  try {
    const hostname = new URL(input.apiUrl ?? "").hostname;
    return hostname === "localhost" ||
      hostname === "127.0.0.1" ||
      hostname === "::1"
      ? token
      : null;
  } catch {
    return null;
  }
}

export function guestCaptchaPlanForEnvironment(input: {
  nodeEnv: string | undefined;
  apiUrl: string | undefined;
  localQaToken: string | undefined;
  turnstileSiteKey: string | undefined;
  browserCaptchaToken?: string | null;
}): GuestCaptchaPlan {
  const token = guestCaptchaTokenForEnvironment(input);
  if (token) return { kind: "token", token };
  const siteKey = input.turnstileSiteKey?.trim() ?? "";
  if (input.nodeEnv === "production" && siteKey) {
    return { kind: "turnstile", siteKey };
  }
  return { kind: "unavailable" };
}

function guestCaptchaPlan(
  browserCaptchaToken?: string | null,
): GuestCaptchaPlan {
  return guestCaptchaPlanForEnvironment({
    nodeEnv: process.env.NODE_ENV,
    apiUrl: process.env.NEXT_PUBLIC_ARGUS_API_URL,
    localQaToken: process.env.NEXT_PUBLIC_ARGUS_LOCAL_QA_CAPTCHA_TOKEN,
    turnstileSiteKey: process.env.NEXT_PUBLIC_ARGUS_TURNSTILE_SITE_KEY,
    browserCaptchaToken,
  });
}

export const guestCaptchaConfigured =
  guestCaptchaPlan().kind !== "unavailable";

function loadTurnstile(timeoutMs: number): Promise<TurnstileApi> {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return Promise.reject(new Error("Browser CAPTCHA is unavailable."));
  }
  if (window.turnstile) return Promise.resolve(window.turnstile);
  if (turnstileScriptPromise) return turnstileScriptPromise;

  turnstileScriptPromise = new Promise<TurnstileApi>((resolve, reject) => {
    let script = document.getElementById(
      TURNSTILE_SCRIPT_ID,
    ) as HTMLScriptElement | null;
    const cleanupListeners = () => {
      script?.removeEventListener("load", finish);
      script?.removeEventListener("error", fail);
    };
    const timeoutId = window.setTimeout(() => {
      cleanupListeners();
      script?.remove();
      reject(captchaUnavailableError());
    }, Math.max(0, timeoutMs));
    const settle = (complete: () => void) => {
      window.clearTimeout(timeoutId);
      cleanupListeners();
      complete();
    };
    const finish = () => {
      if (window.turnstile) {
        settle(() => resolve(window.turnstile as TurnstileApi));
      } else {
        script?.remove();
        settle(() => reject(new Error("Browser CAPTCHA could not start.")));
      }
    };
    const fail = () => {
      script?.remove();
      settle(() => reject(new Error("Browser CAPTCHA could not load.")));
    };
    if (script) {
      script.addEventListener("load", finish, { once: true });
      script.addEventListener("error", fail, { once: true });
      return;
    }

    script = document.createElement("script");
    script.id = TURNSTILE_SCRIPT_ID;
    script.src = TURNSTILE_SCRIPT_URL;
    script.async = true;
    script.defer = true;
    script.addEventListener("load", finish, { once: true });
    script.addEventListener("error", fail, { once: true });
    document.head.appendChild(script);
  }).catch((error: unknown) => {
    turnstileScriptPromise = null;
    throw error;
  });
  return turnstileScriptPromise;
}

async function createTurnstileShell(
  focusBeforeChallenge: HTMLElement | null,
): Promise<TurnstileShell> {
  const { default: i18n } = await import("./i18n");
  captchaShellSequence += 1;
  const titleId = `argus-captcha-title-${captchaShellSequence}`;
  const root = document.createElement("div");
  root.dataset.testid = "turnstile-challenge-shell";
  root.setAttribute("role", "dialog");
  root.setAttribute("aria-modal", "true");
  root.setAttribute("aria-labelledby", titleId);
  root.setAttribute("aria-hidden", "true");
  root.tabIndex = -1;
  root.className =
    "pointer-events-none fixed inset-0 z-[120] flex items-center justify-center p-4 opacity-0 outline-none transition-opacity duration-200";

  const backdrop = document.createElement("div");
  backdrop.className =
    "absolute inset-0 bg-black/25 backdrop-blur-sm dark:bg-black/65";

  const card = document.createElement("div");
  card.className =
    "relative w-full max-w-[380px] rounded-[24px] border border-black/10 bg-white p-6 text-black dark:border-white/10 dark:bg-[#1f2225] dark:text-white";

  const headingRow = document.createElement("div");
  headingRow.className = "flex items-center justify-center gap-3";

  const spinner = document.createElement("span");
  spinner.setAttribute("aria-hidden", "true");
  spinner.className =
    "h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent";

  const heading = document.createElement("h2");
  heading.id = titleId;
  heading.className =
    "font-display text-[17px] font-medium tracking-tight text-black dark:text-white";
  heading.textContent = i18n.t("auth.captcha.verifying", {
    defaultValue: "Verifying you’re not a bot…",
  });

  const container = document.createElement("div");
  container.className = "mt-5 flex min-h-[65px] items-center justify-center";

  headingRow.append(spinner, heading);
  card.append(headingRow, container);
  root.append(backdrop, card);
  document.body.appendChild(root);

  let destroyed = false;
  let revealed = false;
  const backgroundInertState = new Map<HTMLElement, boolean>();
  const containFocus = (event: FocusEvent) => {
    const target = event.target;
    if (
      destroyed ||
      !revealed ||
      (target instanceof Node && root.contains(target))
    ) {
      return;
    }
    root.focus({ preventScroll: true });
  };

  return {
    container,
    reveal() {
      if (destroyed || revealed) return;
      revealed = true;
      for (const sibling of Array.from(document.body.children)) {
        if (!(sibling instanceof HTMLElement) || sibling === root) continue;
        backgroundInertState.set(sibling, sibling.inert);
        sibling.inert = true;
      }
      document.addEventListener("focusin", containFocus);
      root.classList.remove("pointer-events-none", "opacity-0");
      root.classList.add("opacity-100");
      root.setAttribute("aria-hidden", "false");
      root.focus({ preventScroll: true });
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      document.removeEventListener("focusin", containFocus);
      for (const [sibling, wasInert] of backgroundInertState) {
        if (sibling.isConnected) sibling.inert = wasInert;
      }
      backgroundInertState.clear();
      root.remove();
      if (focusBeforeChallenge?.isConnected) {
        const restoreFocus = () => {
          if (
            !focusBeforeChallenge.isConnected ||
            focusBeforeChallenge.matches(":disabled")
          ) {
            return false;
          }
          focusBeforeChallenge.focus({ preventScroll: true });
          return true;
        };
        const restoreObserver = new MutationObserver(() => {
          if (restoreFocus()) restoreObserver.disconnect();
        });
        restoreObserver.observe(focusBeforeChallenge, {
          attributes: true,
          attributeFilter: ["disabled"],
        });
        window.requestAnimationFrame(() => {
          if (restoreFocus()) restoreObserver.disconnect();
        });
        window.setTimeout(() => restoreObserver.disconnect(), 5_000);
      }
    },
  };
}

function resolvedTurnstileTheme(): "light" | "dark" {
  return document.documentElement.classList.contains("dark")
    ? "dark"
    : "light";
}

export function acquireTurnstileChallenge(input: {
  turnstile: TurnstileApi;
  shell: TurnstileShell;
  siteKey: string;
  timeoutMs: number;
  interactiveTimeoutMs: number;
  theme: "light" | "dark";
}): Promise<string> {
  const {
    turnstile,
    shell,
    siteKey,
    timeoutMs,
    interactiveTimeoutMs,
    theme,
  } = input;
  return new Promise<string>((resolve, reject) => {
    let widgetId = "";
    let widgetRemoved = false;
    let settled = false;
    let timeoutId: ReturnType<typeof globalThis.setTimeout> | null = null;
    const startTimeout = (durationMs: number) => {
      if (timeoutId !== null) globalThis.clearTimeout(timeoutId);
      timeoutId = globalThis.setTimeout(() => {
        fail();
      }, Math.max(0, durationMs));
    };
    const removeWidget = () => {
      if (!widgetId || widgetRemoved) return;
      widgetRemoved = true;
      try {
        turnstile.remove(widgetId);
      } catch {
        // The provider may already have removed a completed widget.
      }
    };
    const cleanup = () => {
      if (timeoutId !== null) globalThis.clearTimeout(timeoutId);
      removeWidget();
      shell.destroy();
    };
    const succeed = (token: string) => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(token);
    };
    function fail() {
      if (settled) return true;
      settled = true;
      cleanup();
      reject(captchaUnavailableError());
      return true;
    }

    try {
      startTimeout(timeoutMs);
      widgetId = turnstile.render(shell.container, {
        sitekey: siteKey,
        appearance: "interaction-only",
        theme,
        callback: succeed,
        "error-callback": fail,
        "expired-callback": () => {
          fail();
        },
        "before-interactive-callback": () => {
          shell.reveal();
          startTimeout(interactiveTimeoutMs);
        },
      });
      if (settled) removeWidget();
    } catch {
      fail();
    }
  });
}

export async function acquireGuestCaptchaToken(
  browserCaptchaToken?: string | null,
): Promise<string> {
  const focusBeforeChallenge =
    typeof document !== "undefined" &&
    document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
  const plan = guestCaptchaPlan(browserCaptchaToken);
  if (plan.kind === "token") return plan.token;
  if (plan.kind === "unavailable") {
    throw new Error(
      "Guest access requires a configured browser CAPTCHA before production exposure.",
    );
  }

  const deadline = Date.now() + CAPTCHA_ACQUISITION_TIMEOUT_MS;
  const turnstile = await loadTurnstile(CAPTCHA_ACQUISITION_TIMEOUT_MS);
  const shell = await createTurnstileShell(focusBeforeChallenge);
  const remainingMs = deadline - Date.now();
  if (remainingMs <= 0) {
    shell.destroy();
    throw captchaUnavailableError();
  }
  return acquireTurnstileChallenge({
    turnstile,
    shell,
    siteKey: plan.siteKey,
    timeoutMs: remainingMs,
    interactiveTimeoutMs: CAPTCHA_INTERACTIVE_TIMEOUT_MS,
    theme: resolvedTurnstileTheme(),
  });
}

export async function acquirePasswordAuthCaptchaToken(): Promise<string> {
  try {
    const token = (await acquireGuestCaptchaToken()).trim();
    if (!token || token.length > 4096) {
      throw new Error("captcha_token_out_of_bounds");
    }
    return token;
  } catch {
    const error = new Error(
      "The browser security check could not be completed.",
    ) as Error & { code: string };
    error.code = "captcha_unavailable";
    throw error;
  }
}
