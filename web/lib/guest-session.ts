import {
  normalizeApiLanguage,
  persistBrowserSession,
  unauthenticatedApiFetch,
} from "./argus-api";
import { acquireGuestCaptchaToken } from "./guest-captcha";

export {
  guestCaptchaConfigured,
  guestCaptchaPlanForEnvironment,
  guestCaptchaTokenForEnvironment,
} from "./guest-captcha";

type GuestSessionInput = {
  language: string | null | undefined;
  captchaToken?: string | null;
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

const browserGuestBootstrapper = createGuestSessionBootstrapper<
  GuestSessionInput,
  GuestBootstrapResponse
>(async ({ language, captchaToken: browserCaptchaToken }) => {
  const captchaToken = await acquireGuestCaptchaToken(browserCaptchaToken);
  return bootstrapGuest({
    captcha_token: captchaToken,
    language: normalizeApiLanguage(language),
  });
});

export function startGuestSession(
  language?: string | null,
  captchaToken?: string | null,
) {
  return browserGuestBootstrapper.run({ language, captchaToken });
}

export function retryGuestSession(
  language?: string | null,
  captchaToken?: string | null,
) {
  browserGuestBootstrapper.reset();
  return startGuestSession(language, captchaToken);
}
