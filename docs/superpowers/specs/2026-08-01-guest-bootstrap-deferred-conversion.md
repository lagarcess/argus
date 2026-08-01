# Guest bootstrap deferred to conversion, not page load — scope note

Status: **IN FLIGHT** in PR #330. This is not integration evidence until that
PR merges; the prerequisite CAPTCHA boundary is delivered through PR #326.

Companion to
[2026-07-31-guest-auth-captcha-ux.md](2026-07-31-guest-auth-captcha-ux.md)
(#321). That note fixes the CAPTCHA widget's behavior wherever it fires.
This note changes *when* it fires. Land #321 first, or at least don't
diverge from its `guest-captcha.ts` changes — this lane reuses that
acquisition function unchanged.

## Why

Founder concern: neither ChatGPT nor Grok verify anything before a visitor
can type. Argus's current design establishes a real identity (Supabase
anonymous auth via `sign_in_anonymously`) — and therefore a CAPTCHA check —
before the user has expressed any intent at all. That's a brand-perception
problem on top of the UX problem #321 already covers: the very first thing
a new guest can encounter is a bot check, not the product.

The natural fix is to defer guest bootstrap to the first action that
actually needs a persisted workspace — most likely the first message send
— rather than firing it on page mount.

## Phase 1 — Audit (required before any implementation)

There is a known, unexplained discrepancy that must be resolved first, not
guessed past. Source in this repo (`web/components/guest/GuestEntry.tsx`,
`web/lib/landing-entry.ts`) shows guest bootstrap firing eagerly in a
`useEffect` on mount whenever `entrySurface === "guest"`. But a live
reproduction against the hosted alpha
(`argus-app-suz5.onrender.com`, running `claude/public-alpha-readiness`)
showed the opposite: the guest could type and send a first message with no
visible auth step, before any guest identity appeared to be established.
These don't agree, and the gap must be understood before changing anything.

Audit questions, answered with evidence (code reading + live reproduction),
not assumption:

1. Does `codex/private-alpha-next` (this integration branch) actually
   exhibit the eager on-mount bootstrap today? Reproduce it directly,
   don't just read the source.
2. Why did the hosted `claude/public-alpha-readiness` deployment behave
   differently? Branch drift, a flag difference, a newer routing change
   upstream of what's in this branch, or something else? Trace it to a
   real cause.
3. What is the earliest point today at which a guest's conversation row
   actually gets created in Supabase — is it tied to the auth bootstrap
   itself, or to the first message send, or something else? This decides
   whether "defer to first send" is even mechanically sound or whether
   something else already depends on the workspace existing earlier.
4. Does `ExpiredGuestSession.tsx`'s restart flow, or any other flow, assume
   a guest session already exists at page load in a way that deferral
   would break?

Report findings before writing any implementation code. If the audit shows
the two branches already agree and my read of `GuestEntry.tsx` was simply
wrong about what's deployed, say so plainly — that changes this note's
premise and the founder should hear that before Phase 2 proceeds.

## Phase 1 gate — hard stop

Do not start Phase 2 until the audit findings are reported and confirmed.
This is the same discipline used elsewhere in this codebase for
inventory-before-build passes — the point is to fix the right thing, once,
not to guess and rework.

## Phase 2 — Locked decisions (once the audit confirms the premise)

1. **Guest bootstrap — and therefore CAPTCHA acquisition — must not fire
   before the user's first action that actually needs a persisted
   workspace.** Landing on the page, reading the copy, and typing must
   never trigger any auth or CAPTCHA network activity by themselves.
2. **The landing/chat composer must accept typed input from a guest with
   no identity established yet.** Typing is free. Only submitting costs
   anything.
3. **When the user does submit, bootstrap + CAPTCHA happen inside that
   submission's own existing loading state** (e.g. whatever shows
   "Understanding your idea..." today) — not as a separate, earlier
   interruption, and not as a second distinct "verifying you" step
   stacked in front of the one the user already expects.
4. **No new onboarding step is introduced.** This must not create
   something PRODUCT.md's "no separate onboarding flow" principle would
   flag — the guest experience should read as one continuous action, not
   landing-then-a-check-then-typing.
5. **Reuses #321's fixed CAPTCHA acquisition unchanged** (timeout, visual
   shell, spinner) — this lane is purely about sequencing, not about
   touching that mechanism again.
6. Workspace/allowance semantics must not change: the seven-day workspace
   window and the per-visitor daily allowance (PRODUCT.md, "Guest Entry")
   stay exactly as they are today — this is a timing change, not a policy
   change.

## Stop and report if

- The audit finds the guest conversation/workspace must exist before the
  composer can meaningfully render, for some reason deeper than "that's
  how it's built today" — report before assuming full deferral is
  mechanically possible.
- Deferring bootstrap breaks `ExpiredGuestSession.tsx`'s restart flow or
  any other flow that currently assumes an existing guest session at page
  load.
- The audit contradicts this note's premise entirely (see Phase 1) — stop
  there rather than implementing Phase 2 against a premise that turned out
  to be wrong.

## Where it stops

Phase 1: a short written report, no code changes, reviewed before
proceeding. Phase 2: one PR (or a small stack, if the audit reveals the
change needs splitting) against `codex/private-alpha-next`, sequenced
after or rebased onto #321's PR. Gates: EN/es-419, hermetic frontend
suite, and recorded evidence (screenshots or a short capture) of a guest
typing and sending a first message with zero visible auth step, followed
by a correctly-established guest session.

## Phase 1 close-out (2026-08-01)

Audit complete, reported and reviewed. Findings, and the two open
questions Phase 1 raised, resolved below. Phase 2 may proceed against
this close-out plus the original locked decisions above — do not re-derive
these from scratch.

1. **Premise fully confirmed — there was no real divergence.**
   `codex/private-alpha-next` and the hosted `claude/public-alpha-readiness`
   deployment both bootstrap eagerly on mount, identically, via
   `GuestEntry.tsx`'s mount effect. The original audit trigger (a live
   reproduction that looked composer-first, no visible auth step) was a
   false signal: Turnstile resolved invisibly and fast enough that
   identity had already been established silently before anything was
   visibly typed or sent. Treat the two branches as behaviorally
   equivalent on this point going forward.
2. **Mechanically sound, confirmed live.** `POST /auth/guest` creates the
   Supabase anonymous identity, profile, and the seven-day
   `guest_workspaces` row — it does not create a conversation.
   `ChatInterface.tsx` creates the conversation immediately before
   streaming the first accepted message, and a database trigger binds it
   to the guest workspace. The composer needs neither a workspace nor a
   conversation to render or accept typing. Deferral to first send is
   mechanically clean.
3. **`GET /me` is not in scope of the "no auth network activity on load"
   restriction — narrow decision 1 accordingly.** That restriction was
   aimed at *identity-creating* and CAPTCHA-requiring calls specifically —
   the ones that mint a real anonymous user and therefore need a bot-check
   before the visitor has done anything. A read-only, unauthenticated-safe
   `GET /me` session probe never triggers Turnstile, never creates
   anything, and is never visible to the user — it's the same kind of
   invisible session-restore check any web app does on load. Keep it. It
   also resolves the registered-user redirect path for free, with no
   change needed there.
4. **Expiry detection is deferred too, deliberately — no new pre-check
   mechanism.** Today, "this temporary chat has expired" only surfaces
   because eager bootstrap happens to notice the old identity is dead and
   returns `renewed_after_expiry`. Building a new lightweight probe just
   to keep that pre-emptive detection on page load would be its own new
   mechanism, and would reintroduce exactly the kind of "something runs
   before the user acts" pattern this whole note exists to remove.
   Instead: a returning guest with a dead workspace looks identical to a
   brand-new visitor until they act. Their first send naturally surfaces
   the expired state (bootstrap attempted as part of that submission
   returns `renewed_after_expiry`), and routes to `ExpiredGuestSession`
   reactively at that point, not proactively on load. The tradeoff — a
   bookmarked link to a long-dead guest chat won't announce itself as
   expired until used — is accepted.
5. **`ExpiredGuestSession.tsx`'s restart flow needs its trigger condition
   changed, not its internals.** It currently reaches its authenticated
   state only because `GuestEntry` eagerly creates the replacement
   identity first. Under deferral, `/chat` must represent "guest not
   bootstrapped yet" as its own explicit state (distinct from
   "registered" and from "expired") and run bootstrap — inline, as part of
   the user's first submit — before allowance checks and conversation
   creation, per decision 4's reactive-detection resolution. `Recents`
   already fails open on an early unauthenticated request and needs no
   change.
6. **#321 dependency still holds.** #321 remains open, blocked on PR #319
   landing into this branch (see that spec and the PR #319 reconciliation
   note). `guest-captcha.ts` stays no-touch for this lane until #321's
   acquisition changes are actually present on `codex/private-alpha-next`
   — verify that before Phase 2 starts, don't assume it landed just
   because time has passed.

Phase 2 should build from the current `codex/private-alpha-next` tip at
the time work starts, not from the Phase 1 audit's checkout — this branch
has kept moving (avatar themes, auth copy polish, and others have landed
since the audit ran).
