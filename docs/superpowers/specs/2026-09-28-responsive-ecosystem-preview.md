# Responsive Argus ecosystem web preview

A local, runnable desktop/tablet translation of the locked mobile ecosystem,
with narrow-width support and explicit sample boundaries.

Founder assignment: September 28, 2026. Execution is limited to this preview.

## 1. Why

MVEE sections 2, 3, 7 and 12 define one Argus experience across native mobile
and web. This lane establishes navigation, reading space and reusable UI seams
before financial API wiring. It preserves the existing chat, research and
historical simulation application.

The fetched integration base is
`4b84e054a0d8079b21f38784335ad3241809b4cd`.
The isolated worker is `codex/ecosystem-web-preview` in worktree `587e`.

### Reference state verified at intake

| Reference | Current state | Inspected head |
| --- | --- | --- |
| [Mobile publication #727](https://github.com/lagarcess/argus/pull/727) | Open, unmerged | `802b82306cc29373d7e4dce44c17d33adb243e30` |
| [iPhone foundation #729](https://github.com/lagarcess/argus/pull/729) | Open, unmerged | `b422d986bcf068b56e07283481de373ba8e30dc0` |
| [Android foundation #730](https://github.com/lagarcess/argus/pull/730) | Open, unmerged | `edc43cb7961b68e7ca699a4101510a79667d1a7f` |

#727's final archive is the visual reference, not production source. Its
verified SHA-256 is
`c55e565aa142e38eec61b570510af1c4c2cb9629c24f3ce2d01387639f0ea0e6`.
The published September 28 decisions refine the older integration docs:
guest chat remains available, ecosystem actions require registration, Home
leads with recorded position, and settings uses App / Account / Support.
This assignment explicitly requests that publication. No reference branch or
canonical document is merged or rewritten by this lane.

## 2. Locked decisions

1. Own only `web/app/dev/ecosystem/**`, focused `web/__tests__/ecosystem-preview*`
   and `web/e2e/ecosystem-preview*`, this spec and
   `docs/reports/ecosystem-web-preview.md` with its evidence directory.
2. `/dev/ecosystem` uses the existing development-page pattern: a server-side
   production `notFound()` guard and dynamic rendering. There are no links from
   production entry points. Production root, `/chat`, login and signup remain
   unchanged. Local launch uses the established Spanish flag.
3. Preserve Home / Accounts / Argus / Plan / Search in that order; Updates and
   settings remain header destinations. Start at cold Argus, matching Android;
   iOS currently starts at Home. Initial destination is not a shared design
   lock. Direct query links can open other destinations.
4. Desktop has a quiet persistent labeled rail and a bounded reading canvas.
   Home and Plan may pair primary content with related context; Accounts and
   Search use list/detail space where useful. Tablet compacts the rail; narrow
   widths use the five-destination bottom navigation. No stretched phone frame,
   dense dashboard, or duplicated navigation.
5. Use existing fonts, semantic tokens, logo and Lucide icons. Style only the
   new route. Flat content, calm dividers, generous space and muted emphasis
   follow the locked reference. No new design system or shared token edits.
6. A separate reviewer control selects Guest view or Sample workspace and
   sample/empty/loading/error states. These are demonstration states, never an
   authentication switch. Persistent disclosure says the preview uses fictional
   data, makes no model calls and saves no financial records.
7. Guest surfaces are inspectable. Ecosystem actions first show a registration
   handoff explaining that registration and return-to-action are not connected
   here. Explicit links may leave the preview for existing signup/login/chat;
   no automatic navigation, prefetch, session bootstrap or provider requests.
   The preview cannot authenticate, authorize or unlock a real operation.
8. Home presents currency-separated recorded position, dated source/coverage,
   upcoming commitments and short account/activity lists. DOP and USD never
   combine. Missing values stay unknown. All amounts are authored display
   samples; no totals, differences, forecasts or financial rules are computed.
9. Accounts demonstrates empty/list/detail, manual create and edit layouts,
   reopening a sample account, and a correction-review presentation. Creation
   asks only type, currency, optional nickname and optional starting value.
   Type selection collapses to a summary with Change. Additional details belong
   in Edit details after reopening; financial activity notes are capped at 200
   characters. Values entered into a preview form remain an unsaved
   draft, never update balances or become a financial record. Correction review
   uses a fixed example with previous/observed values, date, basis and explicit
   discrepancy; it distinguishes missing activity from a balance adjustment.
10. Plan separates planned and recorded activity. Search filters local sample
    entries and returns to their owning preview surfaces. Updates explains a
    sample change and links to its source. Settings has Personal details, App,
    Account and Support; unsupported controls explain their limitation.
11. Chat retains stable Recents/New left, Temporary right and a restrained
    title. The disconnected composer accepts an unsent draft, Enter and explicit
    actions produce a local limitation notice, and no fake assistant response,
    streaming or model work is shown. Draft and recent selection survive
    destination changes. Temporary presentation promises no implemented
    retention/privacy behavior. Existing confirmation/result presentation is
    reused only where callbacks can be inert; otherwise document its live seam.
12. Light / Dark / System use the root `ThemeProvider`, `AppearanceModal` and
    registered `argus-theme` persistence. Language uses existing i18next and
    browser language persistence with English/es-419. A no-profile
    `LanguageModal` is appropriate; do not call profile writes or claim account
    synchronization. New bilingual copy stays colocated with the preview.
13. Reuse `AdaptivePanel` / shared overlay ownership for dialogs, Escape,
    browser Back and focus restoration. Destination changes participate in
    browser history. Keyboard focus, scrolling, long labels, 200% text and
    reduced motion must remain usable.
14. No chart library or calculation is added. Any readout is a labeled fixed
    display fixture; Home has no decorative chart. Chart implementation belongs
    to the separate prototype lane. Coordinate its future slot without importing
    or editing that owner's work.
15. Keep loading/error states explicit and reviewer-selected. Retry returns
    to a local sample state. No timer, status or toast implies server work,
    persistence, successful auth or accepted financial mutation.

### Layout sketch

```text
Desktop                  Tablet                 Narrow
rail | header             rail | header           header
     | main + context          | reading canvas   reading canvas
     | bounded chat            | bounded chat     composer when in chat
     | composer                | composer         five-item bottom nav
```

### Existing owners and reuse map

| Capability | Existing owner | This lane |
| --- | --- | --- |
| App navigation / session | `web/components/sidebar/ChatSidebar.tsx`, `web/components/ChatInterface.tsx` | Read for behavior; separate local nav avoids live application hooks |
| Chat title / identity | `web/components/chat/ChatHeaderTitle.tsx`, `web/components/ArgusLogo.tsx` | Reuse safe rendering |
| Composer | `web/components/chat/ChatInput.tsx` | Disconnected local adapter; existing `@` discovery can call providers |
| Recents / history | Existing sidebar/history components and backend projection | Local labeled rows; preserve production owner, no inferred liveness |
| Authentication | Existing landing/auth and guest conversion | Explicit outbound handoff links only; no recreated auth form |
| Confirmations / results | `web/components/chat/` presentation and dev result playground | Reuse read-only/inert seams when safe; no financial-record contract inferred |
| Settings / theme / language | `web/components/settings/{AppearanceModal,LanguageModal}.tsx`, root providers | Direct reuse, without profile callback |
| Dialogs / back / focus | `AdaptivePanel`, `useModalSurface`, overlay stack | Direct reuse |
| Typography / color | `web/app/layout.tsx`, `web/app/globals.css` | Read/reuse; no changes |
| Browser storage | `web/lib/browser-storage.ts` | Existing theme/language only; no financial fixture persistence |
| Financial records / plans | No authorized production UI/API in this lane | New colocated fixture presentation only |

The final report refines exact paths and implementation choices after the full
reuse audit. Importing an effectful component is not reuse if it violates the
fixture boundary.

## 3. Reserved / parked scope

- Production web replacement, exposure, merge, deployment or hosted changes.
- Financial APIs, persistence, posting/reconciliation, calculations and charts.
- Auth endpoint/enforcement changes or simulated server authorization.
- Runtime, prompts, research/backtest contracts, provider integrations, voice,
  file upload, banking, migrations, billing, analytics and financial rules.
- Frozen archive edits, native implementation edits and global/shared UI edits.
- Household permissions or real invitations; sample context is only a visual
  explanation, never authorization or cross-user data.

## 4. Contract gates

No API/schema/data contract changes. Canonical technical owners remain intact.
The spec and final reuse/evidence/handoff report own this development preview's
contract. Shared components and design tokens are dependencies, not owned files.
Any necessary shared change requires coordination before editing that surface.

## 5. Execution contract

- One labeled PR targeting `codex/private-alpha-next`. This spec is its first
  commit, before implementation. Internal follow-ups stay in the same PR.
- Bounded implementation and verification agents may own disjoint files; the
  parent owns integration, review decisions, evidence and cleanup. No agent may
  merge, deploy, send real turns or alter shared owners.
- Use existing Bun/Next.js and pinned Playwright. Run frontend lint, tests,
  type/build checks, focused fixture browser tests and the free mocked eval
  harness. Run applicable CI, changed-document links and merged-tree modularity.
- Browser acceptance covers 1440px desktop, 834px tablet and 390px/360px narrow,
  both languages, light/dark/system persistence and system changes, keyboard,
  focus/dialog/back behavior, scroll reachability, long labels and 200% text.
  Observe network requests and fail on preview API/provider traffic. Verify the
  route renders the server not-found result in a production build and existing
  entry points still render. Measured Next.js 16 streaming behavior sends HTTP
  200 with an explicit not-found marker for this existing dev-route pattern;
  the gate must reject preview markup and require that marker for a 200 response.
  A transport-level 404 would require the shared proxy owner and is outside this
  route-local lane.
- Commit screenshots and interaction evidence under
  `docs/reports/evidence/ecosystem-web-preview/`. Record exact code head,
  environment, fixtures and limitations. Later docs/evidence-only commits may
  retain captures only with explicit surface-diff revalidation at the final head.
- Fetch integration before readiness. Compare semantic overlap by runtime,
  contracts, UI owner, migrations, environment and tests; merge newer integration
  one way. Never rebase. Run modularity against the combined tree.
- Complete `argus-review-exhaust`: validate findings, fix relevant causes,
  reply/react/resolve, pass applicable CI, then request one clean latest-delta
  Codex review. Check zero unresolved threads. Write terminal audit only after
  review returns. Stop at a reviewed preview PR; founder retains merge authority.

## 6. Stop conditions

- A required design conflicts with an approved technical contract or would need
  production/global ownership beyond the assigned route: identify the precise
  conflict and coordinate before changing it.
- An interaction requires real authentication, a financial write, calculation,
  provider call or another lane's implementation: leave a truthful handoff and
  complete the independent preview work.
- A verified review finding cannot be safely fixed in scope: report the
  requirement and smallest safe next step; do not weaken acceptance to pass.
- Unavailable environment/review/CI evidence must be reported as unverified,
  never converted into a READY claim.

## Sources

- [Product](../../PRODUCT.md), [authority](../../DOCUMENTATION_AUTHORITY.md),
  [MVEE](../../specs/argus-minimum-viable-ecosystem-experience.md).
- [Architecture](../../ARCHITECTURE.md), [API](../../API_CONTRACT.md),
  [data](../../DATA_MODEL.md), [design](../../../.agent/designs/argus/DESIGN.md).
- Exact #727/#729/#730 references above; archived mobile reports inspected
  read-only. Current integration does not yet contain these publications.
- Inference: the rail/canvas adaptation is this lane's web layout proposal;
  the primary destinations, content hierarchy and mobile interaction locks are
  inherited. No external design or provider claims are introduced.
