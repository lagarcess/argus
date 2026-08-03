# Guest Omnisearch dossier conversion gate

Make guest run dossiers feel complete while keeping durable decision writes
registered-only.

Founder-locked 2026-08-02 in GitHub issue #340, after the guest experience
checkpoint identified the incomplete metric grid and missing decision controls.

## 1. Why

Argus promises frictionless revisit and says every screen should reduce the
distance between a user and a prior idea (`.agent/designs/argus/DESIGN.md`,
"Alpha Product UX Principles"). A guest dossier that removes a core next action
looks broken and loses the conversion moment. This lane keeps the evidence
dossier complete while preserving the server-owned registered-only mutation
boundary in `docs/API_CONTRACT.md`.

## 2. Locked decisions

1. `can_save_decision` remains `false` for guests and direct guest decision
   writes continue returning `403 account_conversion_required`.
2. Every eligible evidence-backed run dossier requested by a client advertising
   `dossier_decision_conversion_v1` includes its backend-owned `decision`
   action. The action carries a typed availability value: `available` or
   `account_conversion_required`. A client without that additive signal keeps
   the legacy omission when the account cannot save decisions; registered
   `available` actions are unaffected.
3. The frontend never invents an evidence id or decision action. It renders and
   routes only the backend-projected action.
4. Selecting Add decision or Edit on a guest dossier opens the existing account
   conversion modal and does not call the decision mutation endpoint.
5. Successful conversion resumes exactly once in the same open Omnisearch
   dossier, against the same run and evidence artifact, with the decision state
   and note from the selected action restored in the editor.
6. The server handoff continues persisting only its existing verified
   `save_decision` summary. Dossier-specific resume context remains ephemeral in
   the browser latch and is never trusted as mutation authority.
7. Sparse metric layouts use the existing two-column definition grid; when the
   count is odd, the final metric spans the full row. This covers one and three
   metrics without a visual empty cell and keeps two and four metrics unchanged.
8. English and Spanish (`es-419`) use the existing localized conversion and
   decision-editor copy. No vendor or capability plumbing appears in user copy.

## 3. Reserved / parked scope

- Decision-history loading (#341) -- serialized on the same surface but owned
  by a separate issue with an unproven backend/read-path cause.
- Guest decision persistence -- explicitly forbidden by #340; changing the
  capability contract requires a separate founder approval gate.
- New conversion modal or durable resume schema -- the shipped conversion
  handoff already preserves and verifies the evidence artifact identity.
- Dossier redesign, new metrics, or dashboard treatment -- this lane repairs
  completeness without expanding the compact evidence surface.
- Hosted configuration, migrations, deployment, or merge -- outside worker-lane
  authority.

## 4. Contract gates

- `docs/API_CONTRACT.md` -- replace guest omission with the typed decision-action
  availability contract and document conversion-gated client behavior.
- `src/argus/api/schemas.py` and `web/lib/run-dossier-contract.ts` -- keep the
  Python and TypeScript action discriminants aligned.
- `X-Argus-Client-Capabilities` -- use the additive
  `dossier_decision_conversion_v1` presentation handshake so rolling API/web
  deploys and already-open legacy tabs fail closed without changing account
  policy or mutation authorization.
- Checked-in OpenAPI artifact -- regenerate if this repository stores the
  affected schema as generated API evidence.
- `docs/DATA_MODEL.md` -- no change; no table, ownership, RLS, or durable state
  changes are permitted.

## 5. Execution contract

- **PR shape:** one narrow Draft PR targeting `codex/private-alpha-next`, with a
  spec commit followed by test-first implementation commits.
- **Proof required before the PR counts as ready:** focused Python dossier/search
  tests; focused Bun dossier, conversion, and command-palette tests; relevant
  type/lint checks; `git diff --check`; guest browser QA in English and Spanish
  proving the balanced metric layout, visible Add decision/Edit control,
  conversion modal, zero pre-conversion mutation, and same-dossier editor resume
  after conversion. Capture guest-session screenshots outside the repository.
- **Independent review:** verify every locked decision against the final diff
  and run the Argus review contract before the readiness claim.
- **Reconciliation:** record original base `6533377c`; fetch integration before
  READY, merge it one-way only if it advanced, and report semantic overlap.
- **Where it stops:** a pushed Draft PR with terminal exact-head CI. The founder
  alone decides whether to merge or deploy.

## 6. Stop conditions

- If the smallest correct implementation changes `can_save_decision`, permits a
  guest write, or needs new RLS/migration behavior, stop and open a separate
  approval gate.
- If issue #341 or another active lane owns `RunDossierView.tsx`,
  `ChatCommandPalette.tsx`, guest conversion state, or dossier action assembly,
  stop and serialize ownership before editing.
- If exact resume requires trusting browser-provided run/evidence identity for a
  mutation, stop; canonical backend action identity must remain the authority.
- If conversion cannot preserve the open dossier without a new durable handoff
  contract, stop and report the contract expansion instead of silently routing
  the user elsewhere.
- If browser QA would require shared environment writes, hosted changes, paid
  live evals, or deployment, stop and request founder direction.

## Sources

### Argus authority

- GitHub issue #340
- `docs/PRODUCT.md` -- Guest Entry and Golden Path
- `docs/ARCHITECTURE.md` -- Guest Identity and Policy Boundary
- `docs/API_CONTRACT.md` -- Guest identity endpoints and dossier actions
- `docs/DATA_MODEL.md` -- decision notes and run dossier read projection
- `.agent/designs/argus/DESIGN.md` -- Alpha Product UX Principles
- `docs/specs/private-alpha-next-roadmap.md` -- guest integrated checkpoint
- `docs/specs/private-alpha-next-decision-memo.md` -- compact evidence dossier

### External inspiration

- None. The result card's shipped guest conversion-resume interaction is the
  repository-owned precedent.

### Inference

- A full-width final metric is the smallest layout correction that removes the
  apparent empty cell without making the narrow dossier panel denser.
- A typed action availability value is safer than a frontend guest check because
  it keeps both action identity and policy server-owned.
