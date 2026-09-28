# Responsive ecosystem preview: reuse and implementation handoff

This lane translates the locked mobile ecosystem into a development-only web
layout. It is not a production financial application or an authentication proof.
The [bounded spec](../superpowers/specs/2026-09-28-responsive-ecosystem-preview.md)
was committed first as `265adac5`.

## Launch and inspect

From the repository root:

```sh
cd web
NEXT_PUBLIC_ENABLE_SPANISH=true NEXT_DIST_DIR=.next-ecosystem-preview \
  bun run dev -- --hostname 127.0.0.1 --port 3197
```

Open [the preview](http://127.0.0.1:3197/dev/ecosystem) or
[Home with sample data](http://127.0.0.1:3197/dev/ecosystem?view=home&state=sample&audience=sample).
Preview controls select fictional sample/empty/loading/error states and Guest
view/Sample workspace. The sample workspace selector does not authenticate.
No backend, credentials or provider service is required.

The production build renders Next.js's not-found result for this route. As with
the existing bottom-sheet development route, Next.js 16 sends that result in an
HTTP 200 streaming shell with an explicit `NEXT_HTTP_ERROR_FALLBACK;404` marker.
No preview markup is rendered. This lane does not expand the shared proxy;
it does not claim transport-level 404 enforcement.

## Reuse map

| Existing owner | Use in this lane | Future wiring boundary |
| --- | --- | --- |
| Root `app/layout.tsx`, `globals.css`, `ArgusLogo` | Existing fonts, semantic background/foreground, theme provider and mark | Shared design owners remain unchanged |
| `settings/AppearanceModal`, `ThemeProvider`, `browser-storage` | Real Light/Dark/System browser preference | Keep the existing `argus-theme` owner, including OS changes |
| `settings/LanguageModal`, `I18nProvider`, `lib/i18n.ts` | Real browser language preference; no profile callback | Registered profiles retain server-owned language; this sample does not synchronize an account |
| `ui/AdaptivePanel`, `BottomSheet`, `useModalSurface` | Shared responsive dialogs, focus, Escape and browser Back | Preserve one overlay/history owner when connecting actions |
| `chat/ChatHeaderTitle`, `ArgusLogo` | Safe presentation without live chat controller | Real conversations still hydrate from the existing runtime |
| `chat/ChatInput` | Layout/interaction reference only | Typing `@` invokes provider-backed discovery; a disconnected local adapter avoids that side effect |
| `chat/EmptyChatGreeting` | Only its guest-safe presentation is eligible for reuse | Registered greeting may request market session data |
| `sidebar/ChatSidebar`, `ChatCommandPalette`, `useRecentConversations` | Navigation/recall reference only | Existing hooks own real session/history/search and mutations; the preview does not mount them |
| `chat/StrategyConfirmationCard`, `StrategyResultCard`, `ToolResultCard` | Safe display seams only, with inert/omitted action callbacks | Backend owns facts, capabilities and actions; never repurpose a strategy as a financial-record schema |
| Existing `/?auth=signup`, `/?auth=login`, `/chat` | Explicit links leaving the preview | Existing auth and guest-chat controls remain authoritative; no automatic bootstrap or synthetic authorization |
| `/dev/bottom-sheet/page.tsx` | Same server-side production `notFound()` and dynamic route pattern | Production exposure requires a separate assignment |

The genuine gaps are the ecosystem navigation/layout, financial-record forms
and review presentation, and the disconnected composer. They live together
under `web/app/dev/ecosystem`; none establishes a second production owner.

## Reference and consistency

Intake inspected all three PRs while open. A fresh GitHub read before
reconciliation verified the updated states below:

| Reference | Current state | Exact current head |
| --- | --- | --- |
| [#727](https://github.com/lagarcess/argus/pull/727) | Merged as `3fa0dd92167791d82ce81c167c490396358c4316` | `f0a64ffb9d70ce5b82491cf8e1803bb8a6ec7431` |
| [#729](https://github.com/lagarcess/argus/pull/729) | Open, unmerged | `f4457f2b44ec7a437743563ebfd9f9fd701118fa` |
| [#730](https://github.com/lagarcess/argus/pull/730) | Open, unmerged | `3f01a7f79493c8a9dae0ec2d30c12bd38898a175` |

The frozen archive passed CRC and matched SHA-256
`c55e565aa142e38eec61b570510af1c4c2cb9629c24f3ce2d01387639f0ea0e6`.
It was inspected from an extracted temporary copy; its source was not modified.
The current lock/catalog takes precedence over older screenshots within that
archive. In particular, creation has no More details section; account reopening
starts at detail; Check balance is distinct from new activity; settings does not
duplicate financial-space management.

The refreshed mobile publication retains the same archive digest. Changes since
the intake heads reconcile integration and clarify document/status wording;
neither native implementation changed. The preview therefore retains its
inspected visual reference.

The native foundations agree on the five destinations, header destinations,
typography, local samples and persistent appearance. They differ on the initial
destination: iOS starts at Home, Android at Argus. This preview defaults to Argus
and supports direct links for every surface. It preserves product identity while
using wider web reading space.

## Wiring handoff

Existing production owners for a later real account journey:

| Capability | Existing web owner | Integration boundary |
| --- | --- | --- |
| Sign in / sign up | `app/page.tsx`, `components/auth/AuthForm.tsx`, `lib/argus-api.ts` | Reuse real validation, CAPTCHA and session establishment. Existing guest conversion preserves chat actions, not financial-account drafts. |
| Recovery / password reset | `app/auth/forgot-password/page.tsx`, `app/api/auth/recovery/route.ts`, `app/auth/recovery/page.tsx`, `app/account/security/page.tsx`, `lib/auth-security.ts` | Keep current delivery, one-time code exchange, password update and session cleanup owners. |
| Email verification / resend | `AuthForm` owns check-email presentation | No general web resend control/helper exists. Backend guest-signup retry can resend only its already-bound unconfirmed destination; do not treat that as a general resend endpoint. |
| Profile | `components/sidebar/ProfileDetailsDialog.tsx`, `ProfileMenu.tsx`, `lib/profile-writes.ts` | Preserve serialized writes and canonical readback. Financial accounts do not belong in profile fields. |
| Account-form presentation | Shared `AdaptivePanel`, `ConfirmDialog`, `useModalSurface`; preview-local `AccountPanels` | Dialog infrastructure is reusable. No existing production financial-account form or correction controller exists. |

The accepted financial API and data contract must supply durable account identity,
allowed facts and validation, authoritative detail/readback, permission and action
availability, source/freshness, correction history and concurrency behavior.
It must distinguish metadata edits, opening balances, missing activity and balance
corrections, and own related Home/Plan/Search/Updates refresh. Registration-to-action
continuation and household access also need explicit server contracts. This report
does not choose endpoints, schemas, posting rules or calculations. Those shared
contracts remain with the backend owner.

- Replace display fixtures only after the financial-record API, permissions and
  posting/reconciliation contracts are separately approved. Amount strings and
  review examples are not a schema or financial algorithm.
- Keep financial samples immutable and drafts unsaved. A local visual action
  must never produce a saved/authenticated claim or update a recorded total.
- Guest registration/return-to-action and server enforcement remain separate
  work. Handoff links demonstrate the destination without implementing access.
- Reconnect chat through the existing single runtime and existing card/action
  contracts. Do not infer intent from fixture text or promote this composer into
  a second chat controller.
- Chart work belongs to the separate prototype owner. The web lane requests
  only a future display seam with currency, period, source and freshness. No
  chart library, forecast calculation or archive ledger is imported.
- Keep preference persistence with the root providers. Only theme and browser
  language persist here; entered financial values and chat drafts do not.

## Integration and evidence identity

| Item | Full SHA |
| --- | --- |
| Original fetched integration base | `4b84e054a0d8079b21f38784335ad3241809b4cd` |
| Fetched integration at reconciliation | `3fa0dd92167791d82ce81c167c490396358c4316` |
| One-way reconciliation merge | `2b3e6cf2589d87c1bc206e8a93511e4c32b95005` |
| Committed browser evidence head | `356720b044133a69da2889314d4f3571813f2968` |

The intervening integration changes are Supabase server-client isolation, Render
hostname/benchmark configuration, and the mobile design publication. Runtime
and API ownership changes are backend-only; no shared web state owner, component,
package, route contract or migration changed. Render's hostname setting does not
control this local preview. Affected integration tests are backend/auth/release
checks. The design-authority overlap was inspected: the merged publication
retains the exact archive already used here. The combined tree passes the
modularity budget. No rebase or worker-to-integration merge was performed.

The [evidence index](evidence/pr-732/README.md) contains 33 screenshots, their
metadata and 29 interaction records. Capture-only hiding of the Next development
indicator is disclosed. Images and metadata are committed together. Local
source/build checks at the reconciliation merge remain applicable to the evidence
head: the two intervening commits alter only the focused production/browser tests.
The terminal PR audit records the final PR head and explicitly revalidates any
later documentation/evidence-only delta. It is written after the final review.

## Verification

- Full fixture browser suite: **29 passed**. Every destination at desktop,
  tablet and narrow widths; English/es-419; Light/Dark/System persistence;
  keyboard/focus/history; draft, correction, Recents and recovery behavior;
  long labels and 200% text. Zero API/external requests or browser exceptions.
- Production gate: **5 passed**. Preview produces the server not-found result;
  existing root/login/signup render and unauthenticated chat keeps its sign-in
  redirect. Inert localhost Supabase configuration avoids live services.
- Frontend suite: **2,193 passed**, 204 files, zero failures.
- Frontend lint: zero errors; eight existing warnings in shared production
  components, none added by this lane.
- Production build and TypeScript: passed. Only Next-generated custom-dist
  additions to `tsconfig.json` were restored; no shared config change is in the PR.
- Changed documentation links, whitespace and combined-tree modularity: passed.
- Independent latest-delta review: clean after fixing overlay handoff and
  empty/no-match Recents recovery. Hosted CI and the final Codex review are
  recorded in [PR #732](https://github.com/lagarcess/argus/pull/732).

Runtime: macOS 27.0 arm64, Bun 1.4.2, Node v26.10.0, Next 16.2.4,
Playwright 1.59.1 / Chromium 147.0.7727.15. CI uses repository-pinned Bun 1.3.14.
This is Chromium acceptance, not a Safari/Firefox or native-device claim.

With the development server running, reproduce from `web`:

```sh
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3197 \
  node node_modules/@playwright/test/cli.js test \
  --config e2e/ecosystem-preview.playwright.config.ts
```

For production isolation, build into `.next-ecosystem-production`, start it on
3198 with `NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:3999` and
`NEXT_PUBLIC_SUPABASE_ANON_KEY=preview-only-unused`, then use the same command
with `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3198` and
`--config e2e/ecosystem-preview-production.playwright.config.ts`. Do not point
these checks at a live backend or reuse authenticated browser state.

The prescribed free mocked backend harness was attempted at the spec head.
Collection of `test_chat_runtime_trajectory_harness.py` failed while importing
SciPy's `_spropack.cpython-310-darwin.so`, with
`__DATA/__thread_bss` reporting a nonzero offset on this macOS environment.
No backend/environment repair is included in this UI lane. The full normal
Linux CI result remains required; a local collection failure is not a pass.

Running the other nine prescribed files collected 237 checks: 235 passed and
two (`test_issue_272_cases_run_the_real_two_stage_measurement_topology` and
`test_issue_339_compound_edit_materializes_complete_confirmation`) failed on
the same SciPy import. No live/model measurement was run.
