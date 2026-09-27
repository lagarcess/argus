# Issue 688: chat browser safety

## Why and authority

[Issue #688](https://github.com/lagarcess/argus/issues/688) assigns two existing
chat safety fixes. MVEE section 3 preserves trusted conversation; PRODUCT,
ARCHITECTURE, API_CONTRACT, DATA_MODEL and DESIGN retain the current runtime,
authentication and rendering contracts. No ecosystem expansion is assigned.

Original fetched integration base: `ab9143c18740c28f582646d405445c01c4c8aff4`.
Branch: `codex/688-chat-browser-safety`; target: `codex/private-alpha-next`.

## Locked decisions

- Markdown must not cause an image fetch without user action. One reusable
  renderer policy preserves readable text and safe ordinary links across
  private/shared chat, research, tool narrative and receipt rendering.
- Inspect legitimate assets before adding an image CSP in the existing header
  owner. No wildcard hosts, competing policy store or production config edit.
- Supabase identity remains canonical. Existing request-session epochs own
  invalidation. Bind sends, conversation creation and recovery to the identity
  that owns the view; never obtain B's credentials for A's pending text.
- Identity switch/logout invalidates requests and private presentation; same-user
  refresh is not a switch. Preserve supported guest bootstrap/conversion.
- Unsent text must not appear, migrate or auto-send in another identity. Existing
  identity-scoped state may retain work only for its owner. UI copy uses EN/es-419.

## Boundaries and coordination

Own web Markdown, existing auth/session/request transport, necessary rendering
headers, focused tests and durable evidence. No analytics, prompts, financial
schema, household permissions, onboarding, backend authorization redesign,
production configuration, paid/provider chat, customer data, merge or deploy.
Issue #640 is deferred transcript freshness; no competing open PR was found on
2026-09-26. Preserve its freshness owner. Open #646 shares ChatMessage rendering;
recheck actual semantic overlap on reconciliation. Parallel workers own image
rendering and auth respectively; release captain owns browser fixtures/evidence
and delivery. Workers must preserve each other's edits.

## Verification

First reproduce original rendering and cross-account request behavior. Use
focused Vitest regressions and controlled local Playwright fixtures with actual
Supabase browser client session storage/events where feasible, simulated tokens
and intercepted network only. Exercise private/shared remote images, two-tab
switch/logout, switch during admission/stream/recovery, same-user token refresh
and legitimate 404 recovery. Distinguish simulation from real authentication.
Store sanitized browser evidence under `docs/reports/evidence/issue-688/`.
Run frontend checks, merged-tree modularity and required CI; inspect final diff.

## Execution contract and stop conditions

Separate scope, image and account commits where practical. Push one focused PR.
Before readiness, fetch/reconcile integration one-way, report original/current
base, merge SHA, overlap, evidence validity and exact head. Complete one clean
latest-delta Codex review and zero unresolved threads; terminal audit follows
review. Founder merges. Unavailable required gates retain draft status.
If existing client contracts cannot enforce account isolation without a second
auth system or backend redesign, document the precise dependency and complete
independent image delivery. Do not expand protected surfaces to force green.
