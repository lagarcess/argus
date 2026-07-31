# Avatar / Monogram Theme — scope note

Light-touch note, not a full argus-lane-delivery spec. Unlike the shortcuts
feature, this one touches durable state, RLS, and a registered-vs-guest
boundary — those specific pieces are locked because a wrong guess here is
expensive to unwind. Pure visual taste (the palette itself) is left open.

## Locked decisions

1. New durable field, `avatar_theme` — a **token/enum** (e.g. `ocean`,
   `plum`, `teal`), never an arbitrary hex value or free color input.
2. A curated set of 6-8 designed themes. No arbitrary colors, no image
   uploads, no Storage bucket, no public profile surface, no sharing
   integration.
3. Registered accounts only. No guest exposure — guests already sit on the
   `authenticated` RLS role for other reasons this cycle (see the
   public-alpha-readiness spec's decision 11); adding a durable
   guest-writable profile field is exactly the kind of surface that needs
   deliberate scoping, not default inclusion.
4. Safe deterministic default for every account — nobody reaches an
   unset/broken state.
5. Existing initial-derivation logic (display name → username → email,
   `ProfileMenu.tsx:83`) is untouched. This feature only adds the theme
   layer underneath the existing letter.
6. Persists across devices and reloads — backend-owned, not local storage.
7. RLS proof is a real contract gate: a user can read/write only their own
   `avatar_theme`, proven, not assumed.

## Left to the agent's taste

- The actual 6-8 theme choices, hues, gradients.
- Exact contrast mechanism — floor requirement is the initial must read
  clearly against its background (basic WCAG contrast), not a prescribed
  formula.
- Where the picker lives in the profile menu and its exact interaction
  pattern.

## Stop and report if

- Passing contrast requires per-theme custom logic beyond a simple
  light/dark foreground toggle.
- Any theme requires an uploaded or externally-hosted asset.

## Contract gates

- Migration: `avatar_theme` column + default value.
- RLS policy covering the new column.
- API contract update (existing profile-update endpoint or a new one —
  agent's call, but must be documented either way) + OpenAPI regen.

## Where it stops

One PR against `codex/private-alpha-next`. EN/es-419 (if the picker has any
labeled UI text), hermetic backend + frontend suites, RLS proof attached.
