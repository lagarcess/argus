# Auth screens — unify on the documented card pattern — scope note

Companion to
[2026-07-31-auth-form-copy-polish.md](2026-07-31-auth-form-copy-polish.md)
(#322). That note is copy/locale content only. This one is layout/visual
only. Keep them as separate PRs — different root cause, different risk.

## Why

Live QA found two different visual languages across the auth surface:
`AuthForm.tsx` (signup/login, used from the landing page and from
`ExpiredGuestSession.tsx`) renders bare, borderless, placeholder-only
inputs floating directly on the page background. `/auth/forgot-password`
renders a bordered card with a heading, description copy, and a labeled
input. Same product, same flow, two different systems.

`.agent/designs/argus/DESIGN.md` has no dedicated auth/forms section, but
it does document "Cards & Containers" (20px radius) as the one real
container pattern in the system. The forgot-password page already follows
that documented pattern; the sign-up/login form follows no documented
pattern at all. Founder-confirmed direction: bring `AuthForm` in line with
the card pattern that's already canonical — not the reverse.

## Locked decisions

1. `AuthForm.tsx` adopts the same bordered-card container treatment
   already used on `/auth/forgot-password` (20px radius per DESIGN.md's
   Cards & Containers scale), rather than inventing a third style or
   stripping the forgot-password page down to match `AuthForm`'s current
   undocumented borderless style.
2. Apply consistently across every surface that renders `AuthForm`: the
   landing page's request/signup/login modes, and `ExpiredGuestSession.tsx`'s
   inline signup/login swap. `/auth/forgot-password` is the reference and
   stays as-is — it's already correct, don't redesign it.
3. `RequestAccess.tsx` (the waitlist form, part of the same landing
   auth-mode switcher) already uses a similar rounded/bordered treatment
   for its "accepted" state — check whether it should adopt the exact same
   card treatment for full consistency across the whole switcher, since a
   visitor moves between `RequestAccess` and `AuthForm` in the same modal
   flow today.
4. This is a container/layout change only. No changes to `AuthForm`'s
   fields, validation, error handling, or submission logic — those stay
   exactly as delivered by #321/#322.
5. Preserve dark mode — `AuthForm.tsx` already carries `dark:` classes
   throughout; the card treatment must too.

## Left to the agent's taste

- Exact internal spacing/padding within the card.
- Whether the "argus" wordmark sits above the card or inside it.
- Transition/animation when switching between request/signup/login modes
  inside the card.

## Stop and report if

- `AuthForm` is embedded inside a parent that's already carded in a way
  that would double up (a card inside a card) — e.g. if
  `ExpiredGuestSession.tsx`'s own section styling would visually stack
  with a newly-carded `AuthForm` inside it. Resolve the containment
  question explicitly rather than shipping a visibly doubled border.

## Where it stops

One PR against `codex/private-alpha-next`. Gates: EN/es-419, hermetic
frontend suite, before/after screenshots (light and dark) of landing
signup, landing login, `ExpiredGuestSession`'s inline signup/login, and
forgot-password shown alongside them as the reference shape.
