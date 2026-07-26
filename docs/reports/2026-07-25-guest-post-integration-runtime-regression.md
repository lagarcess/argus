# Guest post-integration runtime regression observation

Status: **OPEN DIAGNOSIS — GUEST PUBLICATION STOPPED — NO FIX AUTHORIZED**

- Recorded: 2026-07-25
- Stable integration checkpoint: `b7fd6f08c2fb28166bc67a808ffdad0d65164f06`
- Guest branch: `codex/guest-experience`
- Guest exact head: `3f8e61a5bd679fd1be3d09c3b376ce3d54e1c06b`
- Guest integration merge: `292ccee0ff9b518ad71151d6334e0e9676dd1265`
- Guest feature flags during the failing journey: disabled

This report records a release-blocking signal found while reconciling the guest
lane with the Always Progresses integration checkpoint. It does not claim that
PR #268 caused the failure, reopen the whole Always Progresses pillar, or
authorize a speculative change.

## Observed failure

The guest lane's mandatory post-integration browser matrix submitted an ordinary
Apple starter turn twice, including once after restarting the local
infrastructure. Both attempts ended as:

```text
recoverable_failed / agent_runtime_failure
```

No confirmation card appeared. The second attempt recorded seven provider route
receipts, including one timeout and successful fallback activity. It created no
backtest job or Run, performed no hosted write, and produced no browser-console,
page, or failed-request signal outside the recoverable runtime response.

The guest agent reported the following green evidence at the same candidate:

- disposable-PostgreSQL verification: 112 passed;
- local anonymous-Auth verification: 6 passed;
- hermetic runtime/spine and merged chat gates: 1,538 passed;
- focused frontend reconciliation: 166 passed;
- focused backend reconciliation: 480 passed; and
- production build, TypeScript, Ruff, and diff checks passed.

The current remote safekeeping ref matches local guest head `3f8e61a5`. No guest
PR, merge, deployment, feature activation, or tester exposure is authorized
while this diagnosis remains open.

## What the seven receipts do and do not prove

The integrated turn policy permits at most seven real provider attempts.
Primary and fallback attempts each reserve one slot. Seven receipts therefore
make allowance pressure a credible hypothesis, especially after a timeout.

Seven receipts alone do not prove exhaustion. A request for an additional
provider attempt should emit a separate skipped receipt with
`turn_call_allowance_exhausted`. Diagnosis must inspect:

- receipt order, task, tier, outcome, and failure mode;
- `calls_reserved`, `call_allowance_exhausted`, and `blocked_tasks`;
- the first-wins terminal and terminal reason;
- semantic entry and exit progress; and
- the effective environment and provider/model routing.

Do not increase the allowance, change fallback policy, or weaken no-progress
behavior merely because the count equals seven.

## Attribution limits

Pure integration at `b7fd6f08` has completed real-provider turns and the
same-conversation stress journey recorded in
[the Always Progresses stress audit](2026-07-25-always-progresses-post-merge-stress-audit.md).
The guest branch is not byte-identical to integration when its public flags are
off: it also changes shared account context, allowance, chat routing, recovery,
Search, and frontend surfaces.

The failure may therefore be:

1. an integration runtime regression;
2. a guest-only integration or environment defect;
3. provider instability exposing a bounded fallback edge; or
4. a configuration-propagation mismatch.

No category is accepted without exact evidence.

## Bounded next proof

Use the same user prompt, identity class, provider configuration, runtime flags,
and isolated infrastructure on:

1. pure integration `b7fd6f08`; and
2. guest `3f8e61a5` with guest flags disabled.

Reuse existing receipts when sufficient. At most one additional reproduction is
permitted solely to close an evidence gap.

- If integration reproduces, a runtime-owner branch makes the smallest
  correction and proves the exact journey.
- If only guest reproduces, the guest lane owns the correction.
- If neither reproduces and the evidence isolates transient provider failure,
  record the incident without changing runtime policy.

Guest implementation must not absorb a speculative runtime fix. Grounded
discovery and other provider-facing runtime work must preserve this regression
as a focused check, not restart a broad continuity audit.

## Separate presentation observation

Recoverable infrastructure failures currently have two visual shapes:

- a compact recovery footnote when durable ownership binds the failure to its
  originating user message; and
- a full assistant-message treatment when that ownership identity is absent.

That inconsistency is a bounded recovery-presentation follow-up. It is not part
of the runtime root-cause diagnosis and must not be fixed in the guest lane
before ordinary execution is restored.
