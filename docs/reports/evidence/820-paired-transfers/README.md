# Paired transfer local evidence

October 5, 2026. Original integration base is
`875de09ac2115acec42e09060b92878aa5f18eff`. This is a default-off backend slice
of #820. It does not complete the native two-amount flow or enable transfers.

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
