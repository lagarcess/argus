# Auth form copy polish — password hint + casing consistency — scope note

Small, low-risk companion to
[2026-07-31-guest-auth-captcha-ux.md](2026-07-31-guest-auth-captcha-ux.md),
split out deliberately because it's a different root cause (copy/i18n
content, not loading/timeout logic) and should not share a diff with that
fix. Found during the same live QA pass against the hosted alpha
(`argus-app-suz5.onrender.com`, running `claude/public-alpha-readiness`).

## Findings

1. **No password requirement hint anywhere in the UI.** The only
   enforcement is a native `minLength={8}` attribute on the signup password
   `<input>` (`web/components/auth/AuthForm.tsx`). There is no visible copy
   stating the rule before the user hits a validation failure, and native
   browser validation messages aren't localized to the app's own EN/es-419
   i18n — their wording and even language depend on the browser, not Argus.
2. **Copy casing is inconsistent on the same screen.** "already have an
   account? sign in" and "new to argus? Sign up" render partially
   lowercase — this is the actual locale string, not a rendering artifact —
   while sibling buttons "Sign up" / "Sign In" sit right next to them fully
   capitalized. Both signup and login screens show this side by side; it
   reads as unpolished and screenshots badly.

## Locked decisions

1. Add static, always-visible helper copy near the password field on
   signup stating the requirement (minimum 8 characters) before the user
   submits — not just relying on native browser validation. It does not
   need to be dynamic/reactive in this pass (e.g. no live checkmark as the
   user types) — static text is sufficient.
2. Normalize the casing of "already have an account? sign in" and "new to
   argus? Sign up" (and any other auth-adjacent string sharing the same
   pattern) to read consistently with the capitalized buttons already next
   to them on the same screen.
3. Apply the same casing audit to both `web/public/locales/en/common.json`
   and `web/public/locales/es-419/common.json` — check the Spanish strings
   for the same drift rather than assuming this is English-only.
4. Copy/locale content only. No component logic changes, no new props, no
   behavior change.

## Left to the agent's taste

- Exact placement/styling of the password requirement helper text.
- Exact target casing convention (sentence case vs. title case), as long as
  it's applied consistently across the affected strings on both screens.

## Stop and report if

- The lowercase secondary-action text turns out to be a deliberate,
  established design-system convention used elsewhere in Argus (i.e., if
  it's intentional rather than an inconsistency) — confirm before
  "fixing" something that may not be a bug.

## Where it stops

One PR against `codex/private-alpha-next`. Gates: EN/es-419, hermetic
frontend suite, before/after screenshots of both the signup and login
screens.
