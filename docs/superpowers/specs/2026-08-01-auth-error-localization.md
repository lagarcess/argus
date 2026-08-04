# Localize backend auth error codes on the frontend — scope note

Status: **DELIVERED** by PR #325, merged into `codex/private-alpha-next` as
`05fbef06`. Retained as the frontend localization contract.

## Why

Live QA found backend error text reaching the user raw and unlocalized.
`web/lib/argus-api.ts`'s fetch helpers pass the backend's `detail` string
straight through as `error.message`; `AuthForm.tsx`'s catch block only
special-cases one code (`captcha_unavailable`) and renders raw
`error.message` for everything else. A Spanish-language user hitting any
other auth error sees English text regardless of their language setting —
a direct violation of already-written standards: PRODUCT.md's "Surface UI
should reflect selected language" and DESIGN.md's "All static UI strings
must be translatable."

This is smaller than it first looked. The backend already returns a
stable, structured `code` alongside every error `detail`
(`src/argus/api/routers/auth.py`) — the taxonomy already exists. This is a
frontend mapping gap, not a backend design gap.

## Locked decisions

1. **Extend the exact pattern `AuthForm.tsx` already uses for
   `captcha_unavailable`** — a `code → translated message` lookup — to
   cover the rest of the known codes. Don't invent a second mechanism.
2. **Known codes to cover today**, confirmed via `src/argus/api/routers/auth.py`:
   `unauthorized`, `auth_signup_failed`, `too_many_requests`,
   `guest_access_unavailable`, `internal_error`, `account_already_registered`,
   `guest_bootstrap_failed`, `guest_identity_link_failed`,
   `csrf_origin_rejected`, `registered_account_required`,
   `access_request_unavailable`. Re-grep the router before starting —
   confirm this list still matches current source; it may have grown.
3. Every mapped message must exist in both `en` and `es-419` locale files,
   same discipline as the rest of the app.
4. **Any code not in the map falls back to the existing generic message**
   (`auth.errors.generic`) — never show raw backend text, even for a
   future code this map doesn't know about yet. This closes the gap
   permanently, not just for today's known codes.
5. **Where one code covers genuinely different situations with different
   backend `detail` text** — e.g. `too_many_requests` fires for both
   login rate-limiting and guest-session rate-limiting with different
   messages today — confirm whether one shared translated message loses
   meaningful information for the user. If it does, report it rather than
   silently collapsing two distinct situations into one message; that may
   mean the backend needs a more specific code, which is a scope
   escalation to flag, not to quietly fix as a side quest.
6. **Check `web/lib/guest-api.ts`'s `requestAccess` (the waitlist form)
   too** — it's a sibling auth-adjacent flow with its own error handling
   in `RequestAccess.tsx`, and may have the same raw-text gap. Cover it if
   so; report if its error shape doesn't match the auth router's `code`
   pattern.
7. Frontend-only. No backend changes are expected — the backend's `code`
   field is already exactly what's needed.

## Stop and report if

- Any code from decision 2 needs a backend change to disambiguate two
  distinct situations (decision 5) — report, don't silently expand into
  backend work.
- `requestAccess`'s error shape doesn't already carry a comparable `code`
  field — report before building a second, different mapping mechanism
  for it.

## Where it stops

One PR against `codex/private-alpha-next`. Gates: EN/es-419, hermetic
frontend suite, evidence (test or screenshot) of at least a handful of
distinct error codes rendering correctly in both languages, plus the
fallback-to-generic behavior demonstrated for an unmapped/unknown code.
