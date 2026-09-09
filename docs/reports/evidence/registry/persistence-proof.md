# Registry publication and persistence proof

Date: 2026-09-09. These are working-tree checks, before the release captain's
candidate commit. The parent lane owns exact-head verification and PR readiness.
No provider calls, hosted migrations, flag changes, or production writes were used.

## Observable behavior

- Plural typed cards survive final SSE publication and message reload. An empty
  assistant text with a typed answer is terminal. Generic tools create no fake
  backtest run or EvidenceArtifact.
- Ordered private effects match every call and artifact before dispatch. Repeated
  research calls keep separate jobs and usage identities. The last legacy job
  request is removed before compatibility publication, preventing double dispatch.
  Raw effect patches never enter the public final response.
- Recompute edits the existing message using the shared pending-artifact owner
  and message-store compare-and-swap. Zero remains known, the selected blank is
  retained, policy controls editability, and revisions advance once. A concurrent
  edit or newer message refuses the stale write. No stale checkpoint is projected.
- Fresh runtime context retains the existing confirmation, result and failure
  owners while reading current tool revisions. Failed or pending tools do not
  retire a restored confirmation or a prior retry. The exact mocked Spanish
  failure/retry trajectory passes.
- Asynchronous backtests preserve the admitted call and artifact identity through
  the existing immutable run/evidence finalizer. Their typed cards survive JSON
  round trips without recursive references, and replay creates no extra run.
  English and Spanish coverage uses the canonical DCA configuration, including
  zero starting capital, recurring contributions, costs, benchmark and chart.
- New tool and registered-backtest receipts use the shared presentation contract.
  The sanitizer removes private inputs and narrative, freezes editable facts,
  audits identifiers and credential-bearing URLs, and preserves public citations,
  localized facts and visuals. Historical unbound v1 receipts remain readable.

## Deterministic checks

The focused suite passed **377 tests** after extracting publication and settlement
from the chat router. The final type-narrowing changes passed **262 receipt/API
tests**, and the canonical DCA request fixture passed **3 finalizer tests**.

```sh
poetry run pytest \
  tests/test_tool_result_publication.py tests/test_tool_result_recompute.py \
  tests/test_tool_result_receipts.py tests/test_tool_job_binding.py \
  tests/test_registered_backtest_publication.py tests/test_public_excerpt_api.py \
  tests/test_public_excerpt_receipts.py tests/test_public_excerpt_read_path.py \
  tests/test_public_excerpt_language.py tests/test_pending_artifact_lifecycle.py \
  tests/test_pending_card_conflict.py tests/test_result_link_outcome.py \
  tests/test_render_workflow_execution.py tests/test_backtest_jobs_shadow.py \
  tests/research/test_research_evidence.py \
  tests/research/test_registered_research_jobs.py \
  tests/evals/test_chat_runtime_trajectory_harness.py::test_concrete_trajectory_adapters_observe_the_integrated_candidate \
  -q -o addopts=''
```

The neutral import-boundary suite passed **5 tests**, including fresh-process
probes of `tool_job_binding`. Ruff passed on the owned changed surfaces. Targeted
mypy passed on the nine publication, recompute, binding and projection modules;
the broader receipt projector still reports typing findings outside this targeted check.
The router's modularity overage was removed without changing its budget.

## Database race proof

The receipt-source suite passed **9 tests** on isolated PostgreSQL 17. It used the
actual original receipt migration and the new
`20260909183409_add_tool_receipt_sources.sql`, with only dependency tables supplied
by the adjacent bootstrap. This proves the SQL trigger/index behavior; it is not
a full Supabase migration reset or hosted acceptance claim. CI's existing
`tests/test_*_postgres.py` glob runs the same tests against its full local reset.

The first run before the new migration failed on missing source columns. After
applying it, tests proved concurrent duplicate creates produce one live receipt,
source identity cannot mutate, changed revisions fail, message deletion revokes
and preserves a tombstone, and an already deleted conversation cannot be shared.
Two additional races hold an actual source write open, verify the receipt insert
is blocked using `pg_blocking_pids`, commit the edit or deletion, and observe
`public_excerpt_source_changed` or `public_excerpt_source_deleted` with no receipt.

To reproduce on a **new disposable database** (the bootstrap is not idempotent):

```sh
psql "$ARGUS_DISPOSABLE_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f docs/reports/evidence/registry/receipt-test-bootstrap.sql
psql "$ARGUS_DISPOSABLE_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f supabase/migrations/20260807190000_add_public_excerpt_snapshots.sql
psql "$ARGUS_DISPOSABLE_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f supabase/migrations/20260909183409_add_tool_receipt_sources.sql
poetry run pytest tests/test_tool_receipt_sources_postgres.py -q -o addopts=''
```

When using a disposable Supabase database with every migration already applied,
skip the three bootstrap/migration commands and run the test command directly.

## Reproduced failures corrected during implementation

- Missing plural publication and recompute route failed before implementation.
- Fresh metadata fallback dropped the old approval owner; the integrated Spanish
  retry returned 409. Merging tool references into the existing artifact context,
  and requiring a completed answer for supersession, restored the trajectory.
- A copied top-level research request caused a third dispatch for two calls.
  Ordered effects now consume that compatibility request once.
- Backtest evidence's legacy field allowlist dropped the bound card, causing new
  English and Spanish receipts to use v1. The evidence projection now preserves
  the validated card and both tests require v2 from the same presentation.

The implementation worker made no commits. The release captain must finish the
lane's full-suite, browser, scorecard, integration and review requirements.
