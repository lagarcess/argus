# Task 7 final delta-review fixes

## Range

- Base: `3a82579a7d6ec5340fdf7f36e1da5f6da8ce78d1`
- Candidate: the commit containing this report; obtain its exact SHA with
  `git log -1`.
- Scope: confirmed Task 7 evidence, mask, private summary, and frontend
  composition defects only.

## Red evidence

The focused red run selected seven adversarial/evidence tests. Before the
adapter correction, five failed and one authority-preserving normal Retry
already passed:

```text
5 failed, 1 passed, 22 deselected
```

The failures were the stale-job count, repeated fingerprint count, lifecycle
identity count, exact mask equality, and mismatched projected Retry authority.
The ChatInterface integration red failed at module load because
`settleOpenConfirmationsFromFinalPayload` did not exist. The stale-card backend
private evidence assertion passed immediately and proved the existing runtime
already recorded `redirected`.

An additional adversarial test injects two adjacent Retry lifecycle owners and
proves `orphan_turn.duplicate_turn_count == 1`; the normal path proves exactly
one new lifecycle and a duplicate count of zero.

## Corrections

- Replaced all four Task 7 evidence constants with reads from real memory
  message, lifecycle, job, and private execution-summary owners.
- Added fail-closed checks for missing/malformed owner evidence.
- Made expected-fail masks equal the exact observed pairs and removed only nine
  stale `#239` entries.
- Preserved ordinary-text Retry. The UI-only `retry_last_turn` fixture control
  is validated against the persisted projected recovery authority, then its
  canonical text is submitted through the normal route exactly once.
- Derived Retry terminal artifact identity from persisted messages, not the
  fixture or final-response echo.
- Added backend assertions for private `progress_outcome=redirected` and
  `terminal=redirected`.
- Added a ChatInterface final-SSE-payload composition test proving stale old Run
  recovery leaves the newer confirmation and its Run action active.
- Corrected the stale Task 7 report to the complete range and current truth.

The reviewer proposal to send `retry_last_turn` as a backend action was rejected
as out of contract: the backend action vocabulary intentionally excludes it,
and server-owned keyed Retry is limited to the approved response-option path.

## Verification

```text
Owner-evidence/adversarial focused set: 7 passed
Exact Task 7 free gate: 51 passed
Reload guardrails: 66 passed
Focused frontend: 106 passed
Hermetic runtime/spine: 1220 passed
Ruff: passed
ESLint: passed
Next.js production build: passed
Modularity: passed
git diff --check: passed
```

No live provider, browser, database, push, PR, paid eval, or Task 8 action was
performed. The delta is cohesive and independently reversible. A fresh
independent delta review remains the next gate.
