# iPhone financial accounts

Historical scope for the preserved account-only checkpoint. The active
[financial-loop batch](../../specs/argus-execution-board.md#active-financial-loop-batch)
supersedes its sequencing and sample-Home boundary. Retain this document for
source provenance; it does not assign additional work.

## Why

Connect the existing native Accounts destination to the landed registered-only
account API so a person can create, reopen, edit, correct, archive and restore
their own records. This implements the assigned MVEE account setup journey;
Home, Plan, Argus and Search retain explicit sample boundaries.

Original fetched integration: `296195e86c972e846c251d256b3cc211975bfd57`.
Worker: `codex/ios-financial-accounts`, reusing the clean, free 8be2 checkout.
Design: PR #727, merged reference head
`f0a64ffb9d70ce5b82491cf8e1803bb8a6ec7431`, immutable archive hash
`c55e565aa142e38eec61b570510af1c4c2cb9629c24f3ce2d01387639f0ea0e6`.

## Locked decisions

1. Preserve five tabs, tokens, controls, appearance persistence and native auth
   from #729/#738. Use the existing session owner and refresh/revocation path.
2. A bounded session-owned request seam attaches credentials and binds requests
   and results to the authenticated identity epoch. No token export to views.
3. Accounts have list, detail, create, metadata edit, opening/correction with
   reason/history, archive and restore. No delete route or invented activity.
4. Unknown is distinct from known zero. Amount input/output stays an exact
   decimal string; server owns precision, validity, sign and financial rules.
   Dates retain their stored zone. UI labels support English and es-419.
5. Forms retain the account version and opening revision the person saw.
   A stale or uncertain write rereads server truth and requires explicit
   reconciliation; it never silently upgrades tokens and resubmits.
6. Create retries reuse an immutable payload and idempotency key. Drafts survive
   recoverable same-identity failures, but identity retirement clears all
   private records/drafts and rejects late responses.
7. Server flag-off, guest, missing owner record, auth expiry, validation,
   conflict and unavailable states remain truthful and recoverable. No fake saves.
8. Real auth and Postgres local synthetic acceptance is authorized. Production
   exposure stays default-off. No financial cache or offline write queue.

## Ownership and dependencies

Own `ios/` and this spec, focused setup documentation and
`docs/reports/evidence/ios-financial-accounts/`. Package/session work and view
work have separate delegated owners; parent owns local services, acceptance,
review and PR delivery. Preserve concurrent owners' changes.

Dependencies: landed API_CONTRACT section 17.3, DATA_MODEL section 12.1.4,
financial-accounts-first-slice spec, current native session and mobile lock.
No shared canonical documentation or server contract changes are needed.

## Reserved scope and unresolved choices

No backend/migrations/auth-server/guest-conversion changes, transactions,
financial calculations/totals, transfers/imports, providers, voice, household,
chat/runtime/prompts, analytics, billing, physical-device signing or distribution.
Production bundle identity, signing team and release configuration remain
unapproved. Existing simulator-only identity is replaceable. Cross-surface
sync requires a later shared-backend acceptance run by the lead.

## Execution contract

One spec-first implementation PR targeting `codex/private-alpha-next`, labeled
and moved to ready for Codex review. Founder owns merge/deploy decisions.

Local resources: unique `ios-accounts` stack, ports 58400–58419 after fresh
inventory (free at kickoff); no root/shared env mutations. Preserve running
Android/native-proof/sharing stacks. Never touch founder's iPhone17e
`8B7975F1-1338-4966-90E2-770416CAF174`. Reserve idle large simulator
`0335699A-C522-492B-A8C3-8FD3D7CAC06A`, and create a lane-owned compact simulator.
Record owned process/container/device identifiers; stop only owned resources.

Acceptance: deterministic package/controller tests for lossless amounts,
unknown/zero, immutable retries, both concurrency tokens, coded failures,
identity retirement and refresh reuse. Local real auth/Postgres journey covers
create/read/edit/correct/history/archive/restore, API restart and app process
restart, two-user isolation, stale metadata/opening, lost-response replay,
precision/date-zone failures and default-off. Native UI evidence covers two
iPhone sizes, EN/es-419, light/dark, large text, keyboard and accessibility.
Commit screenshots and bounded results with source provenance; never commit
credentials, tokens or personal data. Provide repeatable setup/build/test commands.

Before final readiness: independent scoped review, address real findings,
latest-delta clean review and zero unresolved threads, exact-head CI, fresh
integration reconciliation one-way with semantic overlap report, merged-tree
modularity check and durable terminal audit after review.

## Stop conditions

Escalate missing/contradictory API behavior, an essential change outside owned
paths, resource collisions, required hosted/signing changes, or an automatic
approval rejection. Continue unaffected work. Never substitute fixtures for
claimed real durability or silently bypass a failed acceptance check.

## Sources

- `docs/PRODUCT.md`, `docs/DOCUMENTATION_AUTHORITY.md`, MVEE Accounts scope.
- `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md` section 17.3,
  `docs/DATA_MODEL.md` section 12.1.4.
- `.agent/designs/argus/DESIGN.md`, mobile-design-lock-2026-09-28 report.
- `docs/specs/lanes/financial-accounts-first-slice.md`, lead kickoff.

Inference: memory-only drafts and direct rereads are sufficient for this online
first slice; durable client financial storage would introduce a second owner.
