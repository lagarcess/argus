# Guest/Auth CAPTCHA hang and unstyled challenge widget — scope note

Reproduced live against the hosted alpha (`argus-app-suz5.onrender.com`, running
`claude/public-alpha-readiness`) and confirmed against source. The frontend's
guest bootstrap, signup, and login all share one CAPTCHA acquisition function —
`acquireGuestCaptchaToken` in `web/lib/guest-captcha.ts`, reused by
`acquirePasswordAuthCaptchaToken` for password auth — so this is one root
cause behind all three flows, not three separate bugs.

Founder report that started this: guests see something CAPTCHA-related
immediately on load, it's flaky, hidden, not apparent, and looks stuck when
signing in. Live reproduction confirmed all four properties with a concrete
mechanism for each — see "Findings" below.

## Findings (why this needs fixing)

1. **No timeout on CAPTCHA acquisition.** `acquireGuestCaptchaToken`
   (`web/lib/guest-captcha.ts:128-188`) wraps Turnstile in a bare `Promise`
   that only settles via Turnstile's own `callback` / `error-callback` /
   `expired-callback`. There is no app-level timeout anywhere in the module.
   Live-reproduced: a signup submission left the button on "Creating
   account..." for 15-20 seconds with a zero-size Turnstile container
   (confirmed via DOM inspection: `width: 0, height: 0`) before Turnstile's
   own internal failure eventually fired `error-callback`. That eventual
   failure came from Turnstile giving up on itself, not from any Argus code.
   In a real environment where the Turnstile script partially loads but the
   challenge iframe never completes (ad-blocker, restrictive network), this
   can hang indefinitely, and the only recovery today is a full page reload
   — which discards all typed form fields, since name/email/password live
   only in local React state with no persistence.
2. **Zero visual context when a challenge does render.** The widget
   container (`guest-captcha.ts:140-144`) is a bare `<div>` appended
   straight to `document.body`, styled only
   `fixed left-1/2 top-1/2 z-[100] -translate-x-1/2 -translate-y-1/2`,
   labeled with an `aria-label` that only screen readers can see. No
   heading, no backdrop, nothing visually tying it to the sign-in/signup
   form the user was just interacting with. This is the direct cause of
   "hidden" / "not apparent" / "looks stuck" — a real security check reads
   as a broken UI glitch because it has no chrome at all.
3. **Loading state during the wait is text-only.** `AuthForm.tsx` swaps
   button text to "Creating account…" / "Signing in…" with
   `disabled:opacity-50` and nothing else — no spinner, no progress
   indication. For a wait that can legitimately run into the tens of
   seconds (see #1), a static dimmed button reads as frozen. This is
   inconsistent with `GuestEntry.tsx`'s own loading state, which does use
   an `animate-spin` spinner — the two flows aren't even consistent with
   each other today.

## Locked decisions

1. **Add an app-level timeout wrapping CAPTCHA acquisition.** Do not rely on
   Turnstile's own internal timing to ever settle the promise. On timeout,
   reject with the existing `captcha_unavailable`-coded error — `AuthForm.tsx`
   already special-cases this code and shows a translated, user-facing
   message ("We couldn't complete the security check. Please try again.").
   Reuse that existing contract; don't invent a second error shape.
2. **Pick the timeout duration from real evidence, not a guess.** Test both
   the normal invisible-mode success path and a forced-slow/forced-failure
   path (Turnstile supports test sitekeys that force specific outcomes —
   use one) to make sure the timeout never fires on a legitimately-resolving
   invisible check, only on a genuinely stuck one.
3. **Give the challenge widget a real visual shell when it does need to
   render.** A small labeled container (e.g. "Verifying you're not a
   bot…", localized EN/es-419) with a dimmed backdrop, consistent with
   Argus's existing modal/overlay treatment elsewhere in the app. Not a
   bare unstyled div with only a screen-reader label.
4. **Add a real loading affordance for the CAPTCHA wait itself**, not just
   the existing text swap — a spinner or equivalent, consistent with (or
   reusing) the treatment `GuestEntry.tsx` already uses.
5. **Fix this once, in the shared `guest-captcha.ts` module** — it must
   apply uniformly to guest bootstrap, signup, and login, since all three
   already share this code. Don't patch `AuthForm.tsx`'s call sites
   independently of `GuestEntry.tsx`'s.
6. **No change to when guest bootstrap fires, and no change to the
   Turnstile site-key/plan selection logic.** Whether guest bootstrap
   should fire eagerly on page mount at all is a separate, founder-owned
   product question, explicitly out of scope for this note.
7. No backend/schema changes are expected. If achieving the timeout or the
   widget shell turns out to require a backend contract change, stop and
   report rather than expanding scope.

## Left to the agent's taste

- Exact timeout duration (bounded by decision 2's evidence requirement).
- Exact visual design of the labeled container and backdrop.
- Exact spinner treatment (new vs. reused from `GuestEntry.tsx`).
- Copy wording for the "verifying" label (must be localized EN/es-419).

## Stop and report if

- Achieving the timeout requires changing the backend `/auth/guest`,
  `/auth/signup`, or `/auth/login` contracts.
- The dimmed-backdrop/modal treatment would require building a new shared
  modal primitive that doesn't already exist in the codebase — flag before
  building one from scratch rather than assuming it's in scope here.
- Turnstile's test-sitekey mechanism isn't sufficient to prove the timeout
  behavior deterministically in the hermetic suite — report what evidence
  is achievable instead of shipping unverified timing logic.

## Where it stops

One PR against `codex/private-alpha-next`. Gates: EN/es-419, hermetic
frontend suite, screenshot evidence of both the invisible-success path and
a forced-visible-challenge path, and evidence (test or recorded repro) that
the new timeout actually fires and recovers cleanly in a simulated stuck
scenario.
