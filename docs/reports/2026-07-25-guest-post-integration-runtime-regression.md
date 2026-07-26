# Guest post-integration runtime regression observation

Status: **CLOSED AS A RELEASE BLOCKER — CONFIRMED GUEST DEFECT CORRECTED — DRAFT PR OPEN**

- Recorded: 2026-07-25
- Stable integration checkpoint: `b7fd6f08c2fb28166bc67a808ffdad0d65164f06`
- Guest branch: `codex/guest-experience`
- Failing guest head: `3f8e61a5bd679fd1be3d09c3b376ce3d54e1c06b`
- Guest integration merge: `292ccee0ff9b518ad71151d6334e0e9676dd1265`
- Failing local QA mode: guest access enabled, public-account access disabled
- Checked-in and post-run feature flags: disabled
- Exact integration control: `50dff34c327c96e40a8a7056ae4b58996dcfbdda`
- Correction commit: `5adff1f4b17579e098a873a3a866bf93e732a6ab`
- Verified product-tree head: `4406986d40d6c3a2ce5f1c5aa97b63ced8052b59`
- Automatic Preview merge observed during report closure:
  `9128758b38e192f3ce6bac07f139263444329cb6`
- Draft PR: [#279](https://github.com/lagarcess/argus/pull/279)

This report preserves the release-blocking signal found while reconciling the
guest lane with the Always Progresses integration checkpoint and records its
final disposition. The confirmed guest settlement defect did not belong to PR
#268 or the interpreter runtime, and it did not reopen the broader Always
Progresses pillar.

## Final disposition

Decision-tree disposition:

- the original two browser failures remain **Branch D — causal attribution
  incomplete** because their retained receipts and terminal diagnostics were
  not request-scoped; and
- a separate, reachable **Branch B — guest-owned settlement defect** was
  reproduced, corrected, and verified before publication continued under later
  founder authorization.

Two premises from the initial observation were corrected before changing code:

- the guest QA launcher enabled guest access for the failing browser journey;
  only public-account access stayed disabled, and checked-in defaults were
  restored to false afterward; and
- the retained seven-receipt waterfall covered two `/chat/stream` requests and
  was not grouped by request identity, so it could not be attributed to the
  literal Apple/SPY turn alone.

There was no captured eighth request, skipped receipt,
`turn_call_allowance_exhausted` signal, or blocked task. Seven receipts therefore
did not prove allowance exhaustion, and neither the seven-call ceiling nor
fallback accounting was changed.

The exact integration control submitted:

```text
Compare Apple with SPY over the last 12 months.
```

once as an allowlisted, non-admin registered account. It completed with one user
message, one assistant message, and a reload-stable runnable confirmation whose
typed strategy asset was `AAPL` and benchmark was `SPY`. The request produced
two successful structured provider receipts, no fallback, no job, and no Run.
That one successful control proved the symptom did not reproduce on integration
in that attempt. It did not, by itself, exclude transient provider behavior as a
cause of the earlier unscoped failures.

The earliest reproducible guest-only divergence was message settlement:

- registered settlement supplied tuple-form hour/day windows;
- guest settlement supplied dict-form `guest_session` windows with explicit
  fixed start and end timestamps; and
- `finalize_chat_turn` tuple-unpacked every window before calling the existing
  atomic finalizer RPC.

Direct composition therefore raised:

```text
ValueError: too many values to unpack (expected 2)
```

after a successful assistant terminal but before that terminal could become
durable. The correction reuses the existing dict-or-tuple
`_serialized_usage_limits` normalization boundary. It changes no interpreter,
provider, attempt allowance, first-wins terminal, prompt, or
`src/argus/agent_runtime/**` behavior.

The intended guest account kind selects the fixed lifetime window and exposed
the adapter bug in direct composition. That reproduction had already reached an
assistant terminal, so `no_progress` did not cause the reproduced defect.
Request-scoped first-wins, progress, account-kind, exception, and complete safe
environment facts were not retained for the two historical failures; this
report does not retrofit them.

Red-before-fix evidence:

```text
tests/test_chat_turn_lifecycle_gateway.py::
test_terminal_finalization_serializes_guest_lifetime_window
```

failed at `chat_turn_lifecycle_gateway.py:176` with the `ValueError` above.

Green evidence:

- the focused lifecycle gateway suite passed, 25 tests;
- real local anonymous Auth/PostgREST/PostgreSQL proved one completed assistant
  terminal, one fixed seven-day `guest_session` message unit, and exact replay
  settling zero;
- the combined real local Auth, allowance, and lifecycle matrix passed,
  72 tests with zero skips; and
- the post-fix registered control at `5adff1f4` completed the literal Apple/SPY
  prompt once, settled the registered hour/day windows once, preserved the
  confirmation across reload, and created no guest workspace, job, or Run.

The later production-build guest journey exercised the ordinary localized Apple
starter, refined it to `MSFT` while preserving `SPY` and both requested and
effective date ranges, completed one canonical backtest, and passed browser
Checks 1–10. Checks 11–20 then passed provider-free against the identical served
product tree after a test-only locator correction. The split is recorded
explicitly in Draft PR #279 and remains an exact-SHA staging-canary gate rather
than being presented as one uninterrupted workspace.

The bounded live-provider work stayed within the amended authorizations: one
integration diagnostic turn, one post-fix registered control, one guest Apple
starter, one later founder-authorized MSFT refinement, and one real guest Run.
No paid scorecard or broad live evaluation ran.

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

At the time of observation, the remote safekeeping ref matched
`3f8e61a5` and publication remained stopped. The corrected lane was later
published only as Draft PR #279. It has not been marked ready, merged,
production-deployed, or enabled. The repository's automatic Supabase Preview
check ran after Draft publication; no manual hosted configuration or production
migration was applied by this lane. That integration advanced the remote PR head
from `4406986d` to `9128758b` by merging `main`; its only tree delta was the
existing main-production release manifest, not guest product behavior.

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
The guest branch is not byte-identical to integration in the tested staged mode
(guest access on, public-account access off): it also changes shared account
context, allowance, chat routing, recovery, Search, and frontend surfaces.

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
2. guest `3f8e61a5` in staged QA mode (guest access on, public-account access
   off).

Reuse existing receipts when sufficient. At most one additional reproduction is
permitted solely to close an evidence gap.

- If integration reproduces, a runtime-owner branch makes the smallest
  correction and proves the exact journey.
- If only guest reproduces, the guest lane owns the correction.
- If neither reproduces and the evidence isolates transient provider failure,
  record the incident without changing runtime policy.

The completed diagnosis confirmed that guest implementation did not absorb a
speculative runtime fix. Grounded Discovery and other provider-facing runtime
work should continue to preserve this regression as a focused check, not
restart a broad continuity audit.

## Separate presentation observation

Recoverable infrastructure failures currently have two visual shapes:

- a compact recovery footnote when durable ownership binds the failure to its
  originating user message; and
- a full assistant-message treatment when that ownership identity is absent.

That inconsistency is a bounded recovery-presentation follow-up. It is not part
of the runtime root-cause diagnosis and must not be fixed in the guest lane
before ordinary execution is restored.
