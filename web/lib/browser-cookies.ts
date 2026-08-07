/**
 * Cookies the web app is responsible for, and the disclosure covering each.
 *
 * The backend has its own registry in argus.api.browser_cookies. This one
 * exists because the web tier writes cookies too, by two routes the Python
 * registry never sees:
 *
 *  - lib/supabase-server.ts hands dependency-chosen names to Next's
 *    cookies().set. Those are gated here, at the door, before the write.
 *  - @supabase/ssr's browser client writes to document.cookie itself. We do
 *    not wrap that: intercepting a library's own cookie storage inside the
 *    auth path risks sign-in for a bookkeeping gain. It is covered
 *    behaviourally instead, by the cookie assertions in
 *    e2e/browser-storage-disclosure.spec.ts.
 *
 * Names are patterns because Supabase derives its cookie from the project ref
 * and chunks large values with a .0/.1 suffix, so no literal list can be right.
 */

export type CookieConcept = "sign_in" | "guest_handoff" | "security";

type CookieRule = {
  pattern: RegExp;
  concept: CookieConcept;
  /** Who writes it, so an unfamiliar name is traceable during review. */
  writer: string;
};

export const COOKIE_DISCLOSURE_RULES: readonly CookieRule[] = [
  {
    // sb-<projectRef>-auth-token, plus .0/.1 chunks for large sessions.
    pattern: /^sb-[a-z0-9-]+-auth-token(\.\d+)?$/,
    concept: "sign_in",
    writer: "@supabase/ssr",
  },
  {
    // The PKCE verifier auth-js derives as `${storageKey}-code-verifier`. It
    // is written during sign-in and password reset and discarded once the
    // exchange completes, so it is short-lived but genuinely set on a browser.
    pattern: /^sb-[a-z0-9-]+-auth-token-code-verifier(\.\d+)?$/,
    concept: "sign_in",
    writer: "@supabase/auth-js (PKCE)",
  },
  {
    pattern: /^sb-(auth|refresh)-token$/,
    concept: "sign_in",
    writer: "argus.api.browser_cookies",
  },
  {
    pattern: /^argus-guest-handoff(-id)?$/,
    concept: "guest_handoff",
    writer: "argus.api.browser_cookies",
  },
  {
    // Cloudflare bot management and Turnstile challenge cookies.
    pattern: /^(__cf_bm|cf_clearance|cf_chl_[a-z0-9_]+)$/,
    concept: "security",
    writer: "Cloudflare",
  },
];

/** The disclosure item covering this cookie, or null if nothing covers it. */
export function disclosedCookieConcept(name: string): CookieConcept | null {
  return (
    COOKIE_DISCLOSURE_RULES.find((rule) => rule.pattern.test(name))?.concept ??
    null
  );
}

/**
 * Deliberately a predicate, not a guard that throws.
 *
 * An earlier version asserted inside the Supabase adapter's cookie write. That
 * put a documentation check on the critical path: when the rules missed the
 * PKCE verifier, password reset broke. A stale disclosure must never be able
 * to break sign-in.
 *
 * Enforcement therefore lives where failure is free, not where users are:
 *  - CI observes what a real browser actually kept
 *    (e2e/browser-storage-disclosure.spec.ts)
 *  - CI observes what the backend actually set
 *    (tests/test_browser_cookie_disclosure.py)
 *  - ESLint keeps cookie writes out of page and route code
 *
 * Those fail a build. This function only answers a question.
 */
export function undisclosedCookies(names: readonly string[]): string[] {
  return [...new Set(names)].filter((name) => !disclosedCookieConcept(name)).sort();
}
