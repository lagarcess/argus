# Issue 196 Spanish Static i18n Design

**Status:** Approved for implementation on 2026-07-13

## Goal

Make the Pinned recents heading and Sidebar Preferences modal fully localized in
English and Spanish, while ensuring future Spanish browser canaries fail if
those required labels fall back to English.

## Scope

- Add the required Pinned and Sidebar Preferences keys to both locale bundles.
- Replace the Sidebar Preferences modal's hard-coded close label and English
  default-value fallbacks with localized keys.
- Keep recents group identity typed, so the pinned icon depends on a stable
  group property rather than comparing a translated label.
- Extend the existing Spanish static-smoke contract and run it from the
  private-alpha canary workflow, so the scheduled canary fails before its
  external journey when a required static key or a known English fallback
  returns.
- Run the focused local browser check. This issue neither deploys nor runs the
  external release journey; issue #197 remains responsible for validating the
  strengthened alarm against the deployed building.

## Non-goals

- No Render deployment, real-user canary, release-profile, API, database, or
  runtime changes. Issue #197 remains the owner of the deployed full-path
  canary.
- No changes to `docs/PRODUCT.md` or
  `docs/specs/private-alpha-next-decision-memo.md`.
- No universal source-code scanner for every translation call. Such a scanner
  would be noisy and would expand the issue beyond these required product
  surfaces.

## Options considered

1. **Locale-only patch.** Smallest diff, but the existing parity check remains
   blind when a key is missing in both locales and no browser assertion proves
   the rendered Spanish modal.
2. **Focused required-key contract plus browser assertion (chosen).** The
   current Spanish smoke suite names every required key, validates both locale
   bundles, and checks the affected source uses keys instead of English
   fallbacks. A focused browser test proves the rendered Spanish UI and can be
   reused by a future canary.
3. **Automatic extraction of every `t()` call.** Broader theoretical coverage,
   but dynamic keys and intentional fallbacks would make it fragile; it is not
   needed to prevent this confirmed regression.

## Design

### Locale contract

`chat.history.pinned` and the six modal keys under `settings.sidebar` are
required static product keys. The English and Spanish bundles must both define
them as non-empty strings, and the Spanish values must be Spanish copy. The
modal uses only these keys, including its close control; it no longer passes
English display strings as fallback values.

### Typed recents identity

The sidebar grouping function will return a stable typed property for each
group. The pinned-icon render branch will inspect that property, while `label`
remains presentation-only. Changing locale text therefore cannot change
behavior.

### Reusable canary assertion

The existing Bun Spanish smoke test becomes the reusable static UI alarm. The
private-alpha canary workflow runs that focused test after frontend dependency
installation and before any authenticated Render probes. It verifies both
locale bundles, checks the affected sources use translated keys rather than
English default values, and rejects translated-label state checks. A real local
browser session separately proves the modal renders the expected Spanish copy.

## Verification

1. Extend the Bun Spanish smoke suite with the required keys and source
   assertions, and make the private-alpha canary workflow run that suite. The
   new assertions must fail before the locale and typed-state code changes.
2. Run a real local Spanish browser session through Profile -> Preferences ->
   Sidebar and verify the rendered copy and close-button accessibility name.
3. Run the focused Bun smoke test, the full frontend test suite, lint, and
   `git diff --check`.
4. Review the diff to confirm the only functional changes are locales,
   Sidebar Preferences, recents grouping, and their tests.
