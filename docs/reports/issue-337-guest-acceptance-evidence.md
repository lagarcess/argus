# Issue #337 Guest Acceptance Evidence

Date: 2026-08-03

Status: **PASS on the final PR head**

Candidate identity: `codex/issue-337-clear-stale-attention` at `HEAD`, enforced
by `ARGUS_EXPECTED_CANDIDATE_SHA="$(git rev-parse HEAD)"` when the gate runs.
The literal immutable head SHA and terminal output are recorded on PR #353.
A committed file cannot embed the SHA of the commit that contains the file,
so this report uses the guarded `HEAD` identity instead of claiming an older
functional commit is the final candidate.

Source evidence: G-01/G-02 in
`docs/reports/2026-08-01-current-checkpoint-experience-feedback.md`.

## Acceptance correction

The first #337 browser fixture identified itself as a registered account and
kept the rail visible with two completed-result ticks. That did not represent
the founder-observed Guest session. A Guest has one simulation, so after the
stale clarification tick cleared, the existing two-tick visibility threshold
also hid the legitimate completed-backtest tick.

Red proof reproduced both failures:

- the Guest-shaped deterministic browser replay could not find the activity
  rail when one completed result remained;
- `conversationRailVisible(12, 1)` returned `false`.

The correction retains the 12-message and desktop thresholds and lowers only
the legitimate tick threshold from two to one.

## Review correction: prove the recovered path

The first implementation treated any later active confirmation as recovery.
That could hide an earlier clarification when the confirmation belonged to an
unrelated idea. The corrected projection uses backend-owned transcript
metadata and fails closed:

- result refinements require matching `source_result_run_id` values;
- ordinary clarification recovery prefers a matching `strategy_path_id`;
- the path id originates from the persisted clarification assistant message;
- only typed `continue` or `refine` turns carry that path into an active
  confirmation; a `new_task` drops it;
- legacy transcripts without an explicit path require compatible typed facts;
- missing or conflicting relationship evidence keeps the marker visible.

Relative-date canonicalization and optional-parameter lookup remain covered
without weakening that relationship check.

## Exact-head failure and root cause

Independent verification reproduced a real failure at
`fa06669c38c9a3f890a2ec9ebd033f94d12d2d8e`:

- the issue-specific preflight expected one rail button and found two;
- the rail contained both the completed MSFT tick and `Needed attention`.

The stricter predicate was not the defect. A bounded real Guest workflow was
driven through local Guest Auth, the real `/chat/stream` runtime, LangGraph,
and durable Supabase persistence:

1. “Test buy and hold over the past year.” produced a persisted clarification.
2. “AAPL” produced a persisted active confirmation.
3. The confirmation's `strategy_path_id` exactly matched the persisted
   clarification message id.
4. `source_result_run_id` was absent, as expected for this non-result path.

The deterministic seed differed from that real shape: it generated the
clarification id but discarded it before writing the active confirmation.
The fail-closed rail therefore correctly kept the seed's unproven attention
tick visible.

## Fixture correction

The acceptance replay now derives its confirmation link from the actual
clarification row created by the fixture:

- `seedGuestResolvedClarificationRailHistory` returns the inserted
  `clarificationMessageId`;
- the issue #337 replay passes that id to
  `seedGuestActiveConfirmationFixture`;
- the helper validates the id as a UUID and writes it as top-level
  `strategy_path_id`, matching the real persisted confirmation shape.

No production rail predicate, runtime contract, API contract, database schema,
or localization behavior changed in this correction.

## Integration reconciliation

The original integration base was
`6533377c1a08539136a622a7d53eee20d0efd845`. Before final evidence, current
`origin/codex/private-alpha-next` at
`3136a4160df1afde2299dbe018cc94860ee494f1` was merged normally into the worker
branch; no rebase or force-push occurred.

There was no shared-file overlap. The integration changes did affect opening
asset interpretation, which is semantically adjacent to the G-01/G-02 missing-
asset journey. Both the real workflow metadata probe and the deterministic
Guest rail replay were therefore rerun after reconciliation. Both passed.

## Final acceptance replay

Mode: local production build, real disposable Supabase Guest Auth, durable
Supabase messages/run/usage, no provider turn in the deterministic rail replay,
and no hosted mutation.

The seeded transcript now mirrors the proven durable relationship:

1. One completed MSFT backtest exists as a durable completed run and result
   message.
2. The long transcript contains the earlier typed clarification, “Which asset
   should I test?”
3. The user supplies `AAPL`.
4. The later active AAPL confirmation carries the clarification message id as
   `strategy_path_id` plus the same typed date provenance a real confirmation
   preserves.
5. The page hydrates from the durable API, then reloads and hydrates again.

Observed and asserted before and after reload:

- account kind is `guest`;
- the rail is visible with exactly one tick;
- the surviving tick is `Backtest finished — MSFT · Buy and hold`;
- no `Needed attention` tick exists;
- the completed result chart remains present;
- durable state is exactly 12 messages, one completed run, and one Guest
  simulation unit;
- route receipts: zero;
- cost ledger rows: zero;
- browser safety errors: zero;
- hosted writes: zero;
- credential exposure: zero.

Command:

```bash
ARGUS_EXPECTED_CANDIDATE_SHA="$(git rev-parse HEAD)" \
  ARGUS_GUEST_QA_APP_PORT=3105 \
  ARGUS_GUEST_QA_API_PORT=8015 \
  ARGUS_GUEST_QA_SUPABASE_WORKDIR="$PWD/temp/qa-337-review-stack" \
  ARGUS_GUEST_QA_DB_CONTAINER=supabase_db_argus-337-review \
  bash scripts/qa/run-guest-experience-qa.sh preflight \
  --grep "issue 337 Guest recovery"
```

Result: `1 passed`.

Focused verification also passed:

- frontend rail/hydration/artifact history: `114 passed`;
- backend workflow/reload guardrails: `111 passed`;
- focused frontend ESLint: passed;
- production Next.js build/type check inside the browser gate: passed.

## Sanitized visual evidence

Local evidence pack for the guarded final head:

- `temp/qa-evidence-guest/<exact-head-sha>/authoritative/issue-337-guest-recovered.png`
- `temp/qa-evidence-guest/<exact-head-sha>/authoritative/issue-337-guest-recovered-reload.png`

SHA-256 before reload:
`a097a27c1c70af6a66d6cd38ae6fa1fa8297721573dade9bd19b80b159a6895a`.

SHA-256 after reload:
`a097a27c1c70af6a66d6cd38ae6fa1fa8297721573dade9bd19b80b159a6895a`.

The identical hashes confirm that reload preserved the same visible Guest
result and single completed-backtest rail marker.

## Disposition

**Proven fixed on the guarded final PR head for the source Guest persona.** The
stale clarification marker clears only when durable transcript metadata proves
continuity, the Guest's single legitimate completed-run marker remains visible,
and reload does not regress either result.

The deterministic acceptance replay is provider-free. The separate bounded
real-workflow probe was used only to establish the canonical persisted metadata
shape and to revalidate semantic overlap after integration reconciliation.
