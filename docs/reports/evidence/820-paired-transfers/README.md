# Paired transfer local evidence

October 5, 2026. Original integration base is
`875de09ac2115acec42e09060b92878aa5f18eff`. This is a default-off backend slice
of #820. It does not complete the native two-amount flow or enable transfers.

## Shared Plan denomination review fix

The [P1 review](https://github.com/lagarcess/argus/pull/854#issuecomment-5999583701)
reproduced a shared DOP Goal publishing a private USD source amount as DOP after
correction. The untouched PR head was
`334e1dcb37c1006f51fbe6e780831cf9e2c2a048`. Credit was already unknown, but the
full public amount bypassed the complete denomination check.

The projection now derives both decisions from `activity_in_currency`. An
unsupported denomination publishes null `amount_minor`. A valid DOP amount
remains visible when an account change requires review. No destination amount
is substituted and no Plan credit rule is expanded.

The [failing-before regression](shared-denomination-red.txt) records two failures,
both `assert '100' == None`, and one passing DOP control. The real PostgreSQL
test creates a consented 20 DOP contribution, corrects the original through
MoneyService, and reads the shared Goal as its owner without private account
grants. It covers both mixed directions and a DOP-only account change.
It verifies null credit, private original/account/note redaction, denied
correction, unchanged account records and no extra receipts for either actor.

The [affected suite](shared-denomination-focused.txt) passes 232 tests with
zero failures and zero skips. The 57 warnings are the existing psycopg-pool
deprecation. The [final focused run](shared-denomination-green.txt) passes all
four Household paired-transfer tests after formatting and the final receipt
assertion. The [original review probe](shared-denomination-probe.txt) now returns
null public amount and passes. These runs use the supplied isolated Python
3.11.15 runtime, synthetic configuration and local PostgreSQL on port 60332.
Existing UUID fixtures remove their records after each run.

Focused Ruff, formatting, whitespace and worker-tree modularity checks pass.
OpenAPI compatibility is included in the 232-test run. The bounded no-comments
review found no added comments or suppressions to remove. The root retains
integration reconciliation and final independent correctness review ownership.

## Reproduction and verification

On the untouched baseline, a synthetic USD/DOP transfer fails with
`currency_mismatch`. Both accounts remain at version 1 without activity.
The first new explicit-pair test fails before implementation with Pydantic
`destination_amount: Extra inputs are not permitted`. After implementation,
[the main focused run](local-tests.txt) passes **193 tests, zero failures and
zero skips**. [API and shared Plan bridge checks](api-shared-tests.txt) pass
**36 tests, zero failures and zero skips**. These runs contain 26 and 28
existing psycopg-pool deprecation warnings respectively. No warning was suppressed.

Tests execute with `env -i`, an explicit worktree `PYTHONPATH` and the existing
Python 3.10.20 runtime. `ARGUS_DISPOSABLE_DATABASE_URL` points only at the root
coordinator's migrated isolated local PostgreSQL on port 60332. Synthetic UUID
identities are created and cleaned by existing fixtures. No root `.env` is loaded.
The initial sandboxed PostgreSQL connection was denied. The accepted local
permission rerun supplied the database evidence. That failed connection is not a
financial correctness failure and is not counted as a passing PostgreSQL run.

The main command is `python -m pytest --no-cov -q` with these suites:

- `tests/financial_accounts/test_paired_transfers.py`
- `tests/test_paired_transfers_postgres.py`
- `tests/household/test_paired_transfers.py`
- `tests/financial_accounts/test_personal_money.py`
- `tests/test_personal_money_postgres.py`
- `tests/financial_accounts/test_goals.py`
- `tests/financial_accounts/test_goal_edges.py`
- `tests/household/test_shared_planning_money.py`
- `tests/household/test_household_financial_boundaries.py`
- `tests/test_openapi_compatibility.py`

The additional API and bridge run names its six suites in its committed log.
The [modularity report](modularity.txt) has no budget violations against the
worker tree. The root merge queue must repeat the check on its combined tree.
Focused Ruff and `git diff --check` pass. OpenAPI is regenerated from the runtime.

## What the checks establish

Actual local PostgreSQL proves independently denominated USD/DOP, JPY/USD and
USD/KWD legs, positive exact precision, receipt replay, changed-pair conflict,
complete corrections and replaced-account retirement. Concurrent response-loss
retries commit one group revision and receipt. A forced failure after both legs
are persisted rolls back records, memberships, receipts and account versions.
A retry after that interruption succeeds once. Unauthorized and stale writes
produce no protected pair effects.

Personal and Household projections hide a private source denomination. A real
Household adapter write and retry preserve the pair. Revoking its source grant
leaves only DOP destination facts in detail and history and blocks correction.
Plan denomination eligibility has one owner, `money_reads.activity_in_currency`.
It requires the complete expected role set and exact count before checking leg
currencies. Empty, partial and duplicated pairs cannot qualify. Mixed transfers
are absent from personal Goal candidates and denied by actual Goal linking.
Shared Plan attachment, candidates, validity and credit use the same predicate.

Frozen preimages are generated from the baseline `MoneyRequest` source.
They preserve ordinary requests, omitted-versus-null refund links, and six real
personal and Household nested command envelopes. The new field uses Pydantic's
existing `exclude_if` support, with no global null omission or schema rewrite.

## Limits and next owner

Backend tests do not prove native presentation, Apple authorization, phone
journeys or hosted state. Native paired entry, preview, history, correction and
persistent retry adaptation remain a separate slice. Physical-phone acceptance
and hosted activation remain open. The dedicated write flag remains false in
the template and Blueprint. No migrations, providers, paid model calls, customer
records or hosted changes were used.

The root owns final code review, integration reconciliation, exact-head CI,
guarded merge and integration landing. This worker performs no merge. The
no-comments reviewer identified three redundant new module docstrings; all
three were removed. No suppression or unresolved code finding remains from
that bounded review. The final independent correctness review is still a root
queue requirement, not an author approval.
