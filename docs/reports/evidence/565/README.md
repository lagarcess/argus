# PR #565 evidence: subtract the guardrails

The finding and the before/after are in
`../../2026-09-08-guardrail-gates-diagnosis.md`. This folder holds the raw
measurements behind the round-two numbers.

## Why the #563 HTTP harness is not the pre-promotion measurement

`scripts/benchmarks/run_turn_latency.py` measures the deployed API, which runs
`main`. A branch cannot be measured through it until promotion, and the
local QA backend needs a `DATABASE_URL` the canonical environment does not
carry. `scripts/benchmarks/interpret_stage_ab.py` therefore runs the same
interpret node the API runs, in-process, under the same seven-call turn
allowance (`turn_execution_scope`), on the #563 cohort messages
(`../issue-462/cohort.json`, same file, same `manifest_sha256`), and records
wall time plus every route receipt. What it measures is the #563 report's
"interpret start to first outcome" interval, which is where the four calls
live; the HTTP, admission, persistence and SSE overhead around it (about 1.7s
in #563) is unchanged by this lane and not re-measured. The deployed #563
numbers remain the product baseline; the founder can re-run the HTTP harness
after promotion.

## Files

- `base-1.jsonl`, `base-2.jsonl`: integration `6bc3e0ee` without this lane's
  changes, run from a sibling worktree on `PYTHONPATH` (the `argus_module`
  provenance line names the tree each run imported). The first pair was
  collected before `source_sha` learned to name the imported tree, so
  `base-1.jsonl` and `head-1.jsonl` carry the invoking worktree's head there;
  `argus_module` is the authoritative line for which tree ran.
- `head-1.jsonl`, `head-2.jsonl`: this lane's head, same venv, same manifest.
- `summary.json`: pooled per-label summary written by `summarize`.
- `live-measurement.json`: the live measurement scorecard at the reconciled
  head `4af15b30`, all categories including the new `ordinary_conversation`
  one: 68 cases, 65 passed, 3 failed, 0 infrastructure errors.
- `baseline-comparison.json`: case-by-case comparison against the
  fingerprint's last measured scorecard, `../411/live-measurement.json` at
  `9fec4bf7`.
- `live-measurement-retry.json`: the three failed cases re-run once on this
  head and once on integration `7de65e26` without this lane's changes,
  value-free (status, checks, recovery code, receipt outcomes). The two
  discovery cases pass on both; the try-next case fails on both, so it is
  pre-existing and filed separately.

Runs were interleaved head, base, head, base so provider drift during the
hour cannot masquerade as a change. Each file records `case_id`, language,
elapsed milliseconds, the interpret outcome, the calls reserved against the
allowance, blocked tasks, and value-free receipts (task, tier, schema, latency,
outcome, fallback, cost, repair effect). No user text, model prose,
identifiers or credentials are stored; `assistant_characters` is a length.

## Reproduction

Recompute the summary without a network request:

```bash
poetry run python scripts/benchmarks/interpret_stage_ab.py summarize \
  docs/reports/evidence/565/base-1.jsonl docs/reports/evidence/565/base-2.jsonl \
  docs/reports/evidence/565/head-1.jsonl docs/reports/evidence/565/head-2.jsonl
```

Collect a fresh sample (paid, real provider calls, no persistence):

```bash
ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider ARGUS_ASSET_PROVIDER_MODE=live_provider \
poetry run python scripts/benchmarks/interpret_stage_ab.py run --execute-live \
  --label head --manifest docs/reports/evidence/issue-462/cohort.json \
  --output temp/guardrails-ab/head-1.jsonl \
  --categories ordinary_chat,compute_intent_probe,confirmation --env-file <env>
```

The research categories are omitted on purpose: the research rail returns
before every audited path, and the #563 receipts show zero guardrail calls on
all thirty research turns, so this lane cannot move them.
