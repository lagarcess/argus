import {
  bootstrapGuest,
  normalizeApiLanguage,
  type GuestBootstrapResponse,
} from "./argus-api";

type GuestSessionInput = {
  language: string | null | undefined;
};

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

function guestCaptchaToken(): string | null {
  if (process.env.NODE_ENV === "production") {
    return null;
  }
  return "argus-local-browser-qa";
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
