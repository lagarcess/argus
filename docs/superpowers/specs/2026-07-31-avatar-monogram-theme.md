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
8. **Palette generation method (added after first attempt landed generic,
   not SOTA):** flat, differently-saturated named colors read as a stock
   default palette, not a designed system — the first attempt's swatches
   didn't share a common DNA (compare how much more saturated the gold
   swatch is than the slate one). Fix:
   - Generate all themes from **one systematic formula** — same
     saturation and lightness, only hue rotates at even intervals around
     the wheel. Picking assorted named colors independently is exactly
     what produced the generic result.
   - Use a **subtle two-stop gradient within the same hue**, not a flat
     single-color fill — a light tint blending toward the base tone, or
     base toward a deeper shade. This is the standard current treatment
     for this exact UI element (Linear, Vercel, Raycast-style monogram
     badges) and is likely the single biggest lever from generic to
     considered.
   - Lean toward a **richer, slightly muted register** — deeper jewel
     tones rather than bright, fully-saturated primary-adjacent colors,
     which read as louder/candy-like and less sophisticated.
   - Render and screenshot the new set before finalizing — this is a
     visual quality bar, verify it visually, don't just describe it.
9. **Scope boundary, unrelated to the palette:** this feature does not
   touch the existing "App language" setting or relocate it from wherever
   it currently lives. If it currently requires reaching it via a
   different entry point (e.g. a top-left icon) than the new avatar
   picker, that access path stays exactly as it was — do not consolidate
   it into the new Profile surface as a side effect of adding the avatar
   picker. If "App language" was already inside this same surface before
   this lane touched anything, say so and this is moot; if it moved,
   revert that specific change.

## Left to the agent's taste

- Exact contrast mechanism — floor requirement is the initial must read
  clearly against its background (basic WCAG contrast), not a prescribed
  formula.
- Where the *avatar picker itself* lives in the profile menu and its
  exact interaction pattern — this freedom does not extend to relocating
  other, pre-existing settings (see decision 9).

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
