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
      theme: "auto";
      callback: (token: string) => void;
      "error-callback": () => boolean;
      "expired-callback": () => void;
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
let turnstileScriptPromise: Promise<TurnstileApi> | null = null;

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

function loadTurnstile(): Promise<TurnstileApi> {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return Promise.reject(new Error("Browser CAPTCHA is unavailable."));
  }
  if (window.turnstile) return Promise.resolve(window.turnstile);
  if (turnstileScriptPromise) return turnstileScriptPromise;

  turnstileScriptPromise = new Promise<TurnstileApi>((resolve, reject) => {
    const finish = () => {
      if (window.turnstile) {
        resolve(window.turnstile);
      } else {
        reject(new Error("Browser CAPTCHA could not start."));
      }
    };
    const fail = () => reject(new Error("Browser CAPTCHA could not load."));
    const existing = document.getElementById(
      TURNSTILE_SCRIPT_ID,
    ) as HTMLScriptElement | null;
    if (existing) {
      existing.addEventListener("load", finish, { once: true });
      existing.addEventListener("error", fail, { once: true });
      return;
    }

    const script = document.createElement("script");
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

export async function acquireGuestCaptchaToken(
  browserCaptchaToken?: string | null,
): Promise<string> {
  const plan = guestCaptchaPlan(browserCaptchaToken);
  if (plan.kind === "token") return plan.token;
  if (plan.kind === "unavailable") {
    throw new Error(
      "Guest access requires a configured browser CAPTCHA before production exposure.",
    );
  }

  const turnstile = await loadTurnstile();
  const container = document.createElement("div");
  container.setAttribute("aria-label", "Security check");
  container.className =
    "fixed left-1/2 top-1/2 z-[100] -translate-x-1/2 -translate-y-1/2";
  document.body.appendChild(container);

  return new Promise<string>((resolve, reject) => {
    let widgetId = "";
    let settled = false;
    const cleanup = () => {
      if (widgetId) {
        try {
          turnstile.remove(widgetId);
        } catch {
          // The provider may already have removed a completed widget.
        }
      }
      container.remove();
    };
    const succeed = (token: string) => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(token);
    };
    const fail = () => {
      if (settled) return true;
      settled = true;
      cleanup();
      reject(new Error("Browser CAPTCHA could not be verified."));
      return true;
    };

    try {
      widgetId = turnstile.render(container, {
        sitekey: plan.siteKey,
        appearance: "interaction-only",
        theme: "auto",
        callback: succeed,
        "error-callback": fail,
        "expired-callback": () => {
          fail();
        },
      });
    } catch {
      fail();
    }
  });
}
