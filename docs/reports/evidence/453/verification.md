# Issue 453 Task 5 verification

## Provenance

- Historical RED base: `8025672924d1c74eb80cc926c72b5d8574b613d7`.
- Task 5 documentation diff base: `55a11cdc992eb622d98c862f171c5dc7c6d85b4b`.
- Prior command execution head: `55a11cdc992eb622d98c862f171c5dc7c6d85b4b`.
- First Task 5 documentation and evidence commit:
  `82e6e59350b07290d9e8ef7cdc070781e4c81cf9`.
- Refreshed command execution head:
  `53e35890ae3173a9a5eedb13d7afd6e14ef10f1c`.

The original RED proof remains in `baseline.md`: the untouched base recorded
`10 failed, 197 deselected` for the issue-specific regression subset. The
documentation change here is additive and does not change any API JSON shape.

## Prior intermediate focused backend suite

Process-local provider and execution guardrails were set without creating or
reading an environment file:

```bash
ARGUS_RUN_LIVE_EVALS=0 \
ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=false \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest --no-cov \
  tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py \
  tests/agent_runtime/test_options_semantic_admission.py \
  tests/agent_runtime/test_validation_failure_copy.py \
  tests/agent_runtime/test_conversation_stages.py -q
```

At the prior command execution head, the result was `205 passed, 12 failed in
7.50s`. This was intermediate evidence, not a terminal readiness claim.

All 12 failures are the same pre-existing shared assertion family:
`test_prose_bearing_contradiction_keeps_verdict_through_readiness_and_admission`
in `test_options_semantic_admission.py`. It expects a model-authored refusal in
`assistant_response`; the locked issue behavior suppresses that field so the
typed clarification stage owns the visible response. The issue-specific
regressions in this command passed. This is a test-expectation mismatch outside
the Task 5 documentation scope, not a documentation regression. Task 3 later
reconciled the 12 now-stale prose-preservation expectations; the refreshed
command below is the current result.

## Refreshed focused backend suite

The exact same command and process-local provider and execution guardrails were
rerun at `53e35890ae3173a9a5eedb13d7afd6e14ef10f1c`.

Result: `217 passed in 6.18s`.

This green deterministic result does not make a terminal readiness claim.
Later branch reconciliation, browser proof, and release gates remain separate
evidence surfaces.

## Refreshed free mocked interpreter evaluation

```bash
ARGUS_RUN_LIVE_EVALS=0 \
ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=false \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest \
  tests/evals/test_measurement_eval_harness.py \
  tests/evals/test_chat_runtime_eval_manifest.py \
  tests/evals/test_chat_runtime_trajectory_harness.py -q
```

The exact command ran at `53e35890ae3173a9a5eedb13d7afd6e14ef10f1c` and
returned `72 passed in 18.83s`. It is the free mocked command from
`tests/evals/README.md`; it did not request live evals or provider execution.

## Contract boundary audit

The current `### Research Responses` section and every byte after it hash to
`d5d1193f1af725bd8aad1b9ab352942affc8ddff1768f5c03c3c18f59ff39d80`.
The same extraction from base SHA
`8025672924d1c74eb80cc926c72b5d8574b613d7` has the identical hash. Task 5
changed only the clarification contract text before that heading.

## Classification

- Baseline: the original issue-specific controls were RED on the untouched
  base, as recorded in `baseline.md`.
- Refreshed fix evidence: the current focused run is green and the free mocked
  interpreter suite is green at the refreshed command execution head.
- Remaining boundary: these deterministic checks do not replace later branch
  reconciliation, browser proof, or release-gate evidence.

# Task 7 terminal deterministic verification

## Exact-head provenance

- Historical integration base:
  `8025672924d1c74eb80cc926c72b5d8574b613d7`.
- Current fetched integration and exact failure-comparison base:
  `c3a9aca181ea43770a81c13ec2fb5f02f85af293`.
- One-way reconciliation merge:
  `b585d429fee633751d5aa19b6668db79165944f9`.
- Retained controlled-browser product source:
  `d87d5d6524e0af89d99dab26cc3e4b6f56c24742`.
- Exact terminal command execution head:
  `4321f1999e8b3d870428cc90c83419d977db6adc`.
- Terminal evidence commit: the later commit that contains this section. It is
  deliberately not described as containing itself.

The intervening integration changes affected runbook, roadmap, Auth template
evidence, backtest math audit/tests, and a Render cron test. They did not share
the issue #453 runtime owner, API clarification section, frontend UI-state
owner, locale catalogs, or focused tests. The final changes after the reviewed
browser source were limited to tests and reports.

## Backend and repository gates

All deterministic provider and execution flags were process-local. No
environment file was read or changed.

| Command | Exact result | Wall time |
| --- | --- | --- |
| `poetry run python -V` | PASS, Python `3.10.20` | `0.38s` |
| `poetry run python .agent/scripts/ownership/verify_branch_ownership.py` | PASS, no ownership policy for the branch, check skipped by policy | `0.25s` |
| `poetry run ruff check .` | PASS, all checks passed | `0.26s` |
| `poetry run ruff format --check .` | Baseline RED, `142` files would reformat and `560` were already formatted | `0.25s` |
| `poetry run python scripts/check_modularity_budget.py` | PASS, no modularity violations | `0.57s` |
| `poetry run pytest --no-cov tests/test_modularity_budget.py -q` | PASS, `8 passed in 1.00s` | `1.82s` |
| `poetry run pytest --no-cov tests/test_i18n_coverage.py -q` | PASS, `4 passed in 0.63s` | `1.41s` |

The same Ruff format command on exact integration
`c3a9aca181ea43770a81c13ec2fb5f02f85af293`, using a writable temporary Ruff
cache, was RED with `144` files that would reformat and `556` already formatted
in `0.29s`. The lane did not create the repository-wide format debt and reduced
the reformat count by two. No formatter was run in write mode.

The full backend command was:

```bash
ARGUS_RUN_LIVE_EVALS=0 \
ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=false \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/ -q
```

Sandbox result: `7 failed, 5050 passed, 495 skipped, 5 warnings in 107.58s`;
wall time `109.93s`. Configured coverage was `TOTAL 45345 6038 87%`.

Six failures were sandbox-only permission failures: the API import probe could
not call its process inspection path, and the seven-test canary-signup module
could not bind a loopback server in the five cases that reached that fixture.
The complete affected subset, one performance node plus all seven canary
nodes, was rerun outside the sandbox and returned `8 passed in 4.39s` with a
`5.15s` wall time.

The remaining sandbox-suite failure was
`tests/test_openrouter_policy.py::test_openrouter_failure_log_reports_raising_origin`.
It expected a file origin but received `<unknown>`. The exact same isolated
node on current integration `c3a9aca181ea43770a81c13ec2fb5f02f85af293`
failed with the same assertion in `1.18s`, wall time `2.18s`. This is a
baseline failure, not an issue #453 regression. There were no lane-only backend
failures.

## Mocked interpreter evaluation

The exact free README command ran with the same three process-local guardrails:

```bash
poetry run pytest \
  tests/evals/test_measurement_eval_harness.py \
  tests/evals/test_chat_runtime_eval_manifest.py \
  tests/evals/test_chat_runtime_trajectory_harness.py -q
```

Result: PASS, `72 passed in 17.24s`, wall time `18.60s`. No live eval or paid
provider path ran. The separately sanctioned live gate remains controller-owned
and is not claimed by this deterministic evidence.

## Web gates

| Command | Exact result | Wall time |
| --- | --- | --- |
| `bun run test` | PASS, `1475` passed, `0` failed across `145` files | `1.19s` |
| `bun run lint` | PASS, `0` errors and `8` existing warnings | `5.70s` |
| `bun x tsc --noEmit` | Baseline-family RED, `6017` diagnostics | `0.90s` |
| `bun run build`, sandbox | Environment RED, Turbopack local-port bind `EPERM` | `166.04s` |
| `bun run build`, outside sandbox | PASS, production build and all routes completed | `5.86s` |

The exact integration TypeScript run produced `6016` diagnostics in `3.00s`,
including one unrelated `TS5033` caused by its read-only worktree. The issue
lane adds exactly two diagnostics in the already-red legacy file
`web/__tests__/chat-recovery-display.test.ts`:

- line `404:16`, `expect(es).toContain("esa regla")`, `TS2349`;
- line `410:16`, `expect(en).toContain("that rule")`, `TS2349`.

Both are the existing Bun `Expectation | callable` typing family already
reported throughout that legacy test. Its count changes from `80` to `82`.
The new focused file
`web/__tests__/issue-453-chat-recovery-display.test.ts` reports zero TypeScript
diagnostics, and no new diagnostic family is introduced. Because the exact
integration checkout contributes the separate `TS5033`, the aggregate count is
`6017` versus `6016`, a net difference of one even though the legacy-file delta
is two.

## Scope, contract, and retained-browser audits

- `git diff --check` passed at the execution head.
- The worktree was clean at the start and after the read-only terminal gates.
- The forbidden-surface diff from historical base through the execution head
  was empty for `render.yaml`, `.env.example`, `.github/argus-env.sh`, `.env`,
  `web/.env.local`, and release-profile paths.
- The verify-workflow environment glob found one tracked example template and
  no non-example environment file. Exact tracked-path checks found neither
  `.env` nor `web/.env.local`. No environment values were accessed or printed.
- The `### Research Responses` section of `docs/API_CONTRACT.md` and every byte
  after it hashes to
  `d5d1193f1af725bd8aad1b9ab352942affc8ddff1768f5c03c3c18f59ff39d80`
  at both historical base and the execution head.
- The seven backend production files, `web/lib/chat-recovery-display.ts`, and
  both locale catalogs are byte-identical from browser-reviewed product source
  `d87d5d6524e0af89d99dab26cc3e4b6f56c24742` through execution head
  `4321f1999e8b3d870428cc90c83419d977db6adc`.
- The controlled-browser receipt still names product source `d87d5d65`, has
  eight after records, reports controlled/provider-free execution, zero console
  and page errors, and `1440x1000` dimensions for every record. Every named
  after screenshot remains non-empty. Because the ten product files are
  byte-identical, the previously accepted bilingual controlled-browser evidence
  is retained rather than recaptured.

## Terminal classification

The issue #453 deterministic lane is clean at execution head
`4321f1999e8b3d870428cc90c83419d977db6adc`: no lane-only backend, frontend,
locale, modularity, build, contract, secret, or forbidden-surface failure
remains. Repository-wide Ruff formatting, TypeScript debt, and the OpenRouter
origin assertion remain explicitly classified against current integration.
This terminal deterministic result does not claim the separately controlled
live eval or hosted release proof.
