# PR #732: responsive ecosystem preview evidence

Code and test head: `356720b044133a69da2889314d4f3571813f2968`.
Every PNG has a sibling JSON file with its exact head, URL, viewport, language,
theme, browser and capture time. `interactions/` records every acceptance case
and its network audit. This is local fixture evidence, not financial API or
authentication evidence.

## Browse the preview

| Surface | Durable capture |
| --- | --- |
| Desktop Home | [English, Light](desktop-en-light-home.png), [Spanish, Dark](desktop-es-dark-home.png) |
| Accounts | [Desktop](desktop-en-light-accounts.png), [Spanish tablet](tablet-es-light-accounts.png), [360px Spanish](compact-es-light-accounts.png) |
| Argus | [Desktop](desktop-en-light-argus.png), [390px](narrow-en-light-argus.png), [unsent draft](guest-unsent-chat-draft.png) |
| Existing DCA card | [English](tablet-en-dca-confirmation.png), [Spanish](tablet-es-419-dca-confirmation.png) |
| Plan | [Desktop](desktop-en-light-plan.png), [Dark tablet](tablet-en-dark-plan.png) |
| Search | [Desktop](desktop-en-light-search.png), [account filter recovery](account-activity-filter-recovery.png) |
| Updates | [Desktop](desktop-en-light-updates.png) |
| Settings | [Desktop](desktop-en-light-settings.png), [Spanish System resolving Dark](settings-spanish-system-dark-persistence.png) |
| Guest action handoff | [Desktop](desktop-en-light-guest-registration-handoff.png), [Spanish narrow](narrow-es-dark-guest-registration-handoff.png) |
| Account forms | [Unsaved creation review](account-create-unsaved-review.png), [reopen/edit](account-reopen-edit-details.png), [correction review](account-correction-review.png) |
| Recents recovery | [Empty](recents-empty-state.png), [no match](recents-unmatched-state.png) |
| Sample states | [Empty](home-empty-state.png), [loading](home-loading-state.png), [error](home-error-state.png) |
| Larger text / long labels | [Desktop at 200% text](desktop-en-light-enlarged-text-long-label.png), [360px Spanish at 200%](compact-es-light-enlarged-text-long-label.png) |

## Method and limits

- Seven matrix cells visit all seven destinations at 1440, 834, 390 and 360px.
  English/es-419 and Light/Dark are covered; a separate interaction checks
  System following OS changes, reload persistence and language changes.
- Browser requests to any API or external origin are blocked and fail the test.
  WebSocket traffic is also guarded. All expected traffic is local assets,
  locale catalogs and the development server.
- Registration click-through uses an inert local destination response. It
  proves overlay/history handoff and one-step Back, not real registration.
- Samples never authenticate or persist records. Only existing browser theme
  and language preferences persist. Financial forms use fictional unsaved text.
- The production gate verifies the server not-found result and absence of
  preview markup. Next.js 16 streams that result with HTTP 200; this is not a
  transport-level 404 assertion. Existing entry checks use inert localhost
  Supabase configuration, no cookies and no CAPTCHA; `/chat` retains its sign-in
  redirect. No live auth service is contacted.
- Chromium is pinned by Playwright 1.59.1. Screenshots use device scale 1,
  reduced motion, local fonts and America/Santo_Domingo time. The Next.js
  development indicator is hidden **only during screenshots**; product content
  is not masked. Increased-text cases explicitly replace a sample label and
  double computed text size, without scaling layout dimensions.
- Desktop/tablet/narrow layout and representative dialog/state images were
  inspected visually. This does not establish Safari/Firefox or native-client
  acceptance, real financial permissions, posting rules or chart behavior.

Reproduce with the commands in the [reuse and wiring handoff](../../ecosystem-web-preview.md).
Final PR-head revalidation, CI and review belong in the terminal PR audit, after
the last review has returned. Later documentation/evidence-only commits retain
these captures only after verifying that their rendered surface is unchanged.
