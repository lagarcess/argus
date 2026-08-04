# Auth screens — unify on the documented card pattern — scope note

Status: **DELIVERED** by PR #328, merged into `codex/private-alpha-next` as
`403ea114`. Retained as the card-ownership and containment record.

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

## Containment gate — resolved (2026-08-01)

The impact-mapping pass found the containment risk was real (both
`ExpiredGuestSession.tsx` and a previously-undiscovered
`GuestConversionModal.tsx` already wrap `AuthForm` in their own card) and
proposed a sound structural fix: standalone `AuthForm` owns the canonical
card by default; an `embedded` visual-only variant suppresses that chrome
for parents that already provide one, so every surface ends up with
exactly one card. Approved, with one important correction to what "the
canonical card" actually is.

1. **The canonical card is DESIGN.md's documented shape — not whatever
   each existing parent already happens to have.** Checked directly:
   `ExpiredGuestSession.tsx` currently uses `rounded-[2rem]` (32px) with
   `shadow-xl`; `GuestConversionModal.tsx` uses `rounded-[28px]` with
   `shadow-2xl`. Both violate DESIGN.md on two counts at once — wrong
   radius (documented card radius is 20px) and a shadow at all
   (`.agent/designs/argus/DESIGN.md`: "Zero shadows — flat is the Argus
   identity," explicitly listed under "Don't"). Keeping either of these
   as "the one card" under the `embedded` label would just preserve two
   existing violations under a new name — normalize both to the
   documented 20px, zero-shadow treatment, don't preserve their current
   styling as-is.
2. **Even `/auth/forgot-password`, this note's original reference, is
   slightly off** — it uses `rounded-[24px]`, not the documented 20px.
   Correct it too, so there is exactly one true radius value across
   every surface (landing `AuthForm`, `ExpiredGuestSession`,
   `GuestConversionModal`, and forgot-password), not three surfaces
   converging on a fourth that was itself a few pixels off.
3. **`GuestConversionModal.tsx` is now explicitly in scope**, on the same
   terms as `ExpiredGuestSession.tsx` (decision 2) — this wasn't in the
   original note because it wasn't found until the impact-mapping pass;
   treat it as a real gap in the original scope, not an out-of-band
   addition to resist.
4. **Drop `RequestAccess.tsx` from this pass — it doesn't exist on
   `codex/private-alpha-next` yet.** It's part of PR #319's payload,
   which hasn't landed on this branch. Decision 3's original wording
   assumed it existed here; it doesn't. Don't block on it — revisit once
   #319 lands, as its own small follow-up if the card treatment needs
   applying there too.
5. Proceed with implementation under this correction. No other change to
   the original locked decisions.
