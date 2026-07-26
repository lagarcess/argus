import {
  normalizeApiLanguage,
  persistBrowserSession,
  unauthenticatedApiFetch,
} from "./argus-api";

type GuestSessionInput = {
  language: string | null | undefined;
};

export type GuestBootstrapResponse = {
  authenticated: true;
  reused: boolean;
  renewed_after_expiry?: boolean;
  public_account_access_enabled?: boolean;
  account_kind: "guest";
  session?: {
    access_token?: string;
    refresh_token?: string;
    expires_in?: number;
  } | null;
  user?: Record<string, unknown> | null;
};

export async function bootstrapGuest(payload: {
  captcha_token: string;
  language: "en" | "es-419";
}) {
  const response = await unauthenticatedApiFetch<GuestBootstrapResponse>(
    "/auth/guest",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
  await persistBrowserSession(response);
  return response;
}

export function createGuestSessionBootstrapper<
  TInput,
  TResult,
>(bootstrap: (input: TInput) => Promise<TResult>) {
  let pending: Promise<TResult> | null = null;

  return {
    run(input: TInput) {
      if (!pending) {
        pending = bootstrap(input).catch((error: unknown) => {
          pending = null;
          throw error;
        });
      }
      return pending;
    },
    reset() {
      pending = null;
    },
  };
}

export function guestCaptchaTokenForEnvironment(input: {
  nodeEnv: string | undefined;
  apiUrl: string | undefined;
  localQaToken: string | undefined;
}): string | null {
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

function guestCaptchaToken(): string | null {
  return guestCaptchaTokenForEnvironment({
    nodeEnv: process.env.NODE_ENV,
    apiUrl: process.env.NEXT_PUBLIC_ARGUS_API_URL,
    localQaToken: process.env.NEXT_PUBLIC_ARGUS_LOCAL_QA_CAPTCHA_TOKEN,
  });
}

const browserGuestBootstrapper = createGuestSessionBootstrapper<
  GuestSessionInput,
  GuestBootstrapResponse
>(async ({ language }) => {
  const captchaToken = guestCaptchaToken();
  if (!captchaToken) {
    throw new Error(
      "Guest access requires a configured browser CAPTCHA before production exposure.",
    );
  }
  return bootstrapGuest({
    captcha_token: captchaToken,
    language: normalizeApiLanguage(language),
  });
});

export function startGuestSession(language?: string | null) {
  return browserGuestBootstrapper.run({ language });
}

export function retryGuestSession(language?: string | null) {
  browserGuestBootstrapper.reset();
  return startGuestSession(language);
}
