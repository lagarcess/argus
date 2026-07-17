# Argus Eval Harness

This folder contains the private-alpha measurement eval harness. Cases live as
data fixtures, and the harness asserts typed runtime outcomes instead of exact
assistant phrasing.

## Test Tiers

- **Mocked harness - every change (free, no API calls):**
  `poetry run pytest tests/evals/test_measurement_eval_harness.py tests/evals/test_chat_runtime_eval_manifest.py tests/evals/test_chat_runtime_trajectory_harness.py`
  Validates routing, state, full conversation-step manifests, and the seven
  session trajectories. This is the everyday inner-loop check.
- **Live eval - only the 3 sanctioned moments:**
  1. Pre-merge on a PR that changes runtime behavior.
  2. Main promotion candidate.
  3. After any model/provider change.
- **Browser QA is also real-API:** every turn spends tokens. Use it at gates, not
  per hypothesis.

## Mocked Run

Run the mocked harness checks with:

```bash
poetry run pytest \
  tests/evals/test_measurement_eval_harness.py \
  tests/evals/test_chat_runtime_eval_manifest.py \
  tests/evals/test_chat_runtime_trajectory_harness.py \
  -q
```

This run is free. It does not call the LLM, does not spend provider tokens, and
is safe to run anywhere.

## Search Provider Evaluation (Issue #244)

Run the bounded Search fixture validator with:

```bash
poetry run pytest tests/evals/test_search_provider_eval.py -q --no-cov
```

This evaluation is also free. It parses clearly labeled, authored synthetic
Perplexity-direct and OpenRouter web-search fixtures and validates their shape.
URL fields, query-term coverage, declared latency/cost, zero-Search scenarios,
outage scenarios, and the normalizer-applied untrusted-source label are fixture
contract behavior only. They do not prove provider relevance, citation quality,
Search routing, runtime policy,
outage recovery, latency, or cost. Changing an `evidence_kind` string cannot
turn a fixture into empirical evidence; every empirical check stays unproven
until a later sanctioned probe supplies independently captured provider and
runtime provenance.

Generate the non-versioned decision evidence with:

```bash
poetry run python -m tests.evals.search_provider_eval
```

The report is written to
`temp/issue-244-search-provider-evaluation.json`. It must recommend deferral
until real provider evidence, issue #241 integration, and explicit founder
activation exist. Its Perplexity-direct next-probe entry is an official-
documentation-based hypothesis, not an empirical provider comparison or
selection. Any public citation/context schema also remains behind its separate
API-contract approval gate.

## Live Run

Run the live harness with:

```bash
ARGUS_RUN_LIVE_EVALS=1 ARGUS_EVAL_ENV_FILE=<path> poetry run pytest tests/evals/test_measurement_eval_live.py -q
```

Warning: this deliberately spends real LLM tokens. Use it when you want to
measure the current real interpret path, not for routine local lint loops.

## When to Run

Run the mocked suite everywhere; it is free and safe.

Run the live suite at exactly three moments:

1. Once pre-merge on any PR that changes runtime behavior.
2. On every `main` promotion candidate, as a full run on the exact SHA with no
   unexpected failures.
3. After any interpreter model or provider change.

Live results can vary. If one failure is surprising, rerun once, then
investigate. Never delete the case to make the run green.

## Scorecards

Live runs write JSON scorecards to:

```text
temp/argus_eval_scorecards/
```

`temp/` is gitignored, so scorecards are local run artifacts. Measurement
scorecards include per-category totals and pass rates. Seven-session scorecards
include stable trajectory labels, operation names, and failure prefixes only;
they omit prompts, SSE payloads, route receipts, and runtime identifiers.

Expected-fail cases never count as passes. They are reported separately so
known broken behavior stays visible.

## Expected-Fail Cases

An expected-fail case must be tagged with an issue number and scoped
`allowed_failures`. Every mask names one exact `step_id` and one failure
`prefix`. The tag only masks that failure family at that step; the same prefix
at another step, or any unrelated failure, still fails the eval.

The lane that fixes the tagged issue must flip the case to pass as part of that
lane's acceptance. Expected-fail is a truthful baseline, not a permanent waiver.
If a tagged case has no failures, its status is `unexpected_pass`, which also
does not count as a pass. Remove the tag only after verifying the owning issue's
full acceptance criteria.

## Seven Alpha Session Trajectories

`alpha_session_trajectories.json` is an append-only, sanitized fixture set with
stable labels `alpha_session_01` through `alpha_session_07`. The typed adapter
runner dispatches every user or action step through stream, action, disconnect,
reload, retry, or persistence adapters. A disconnect step owns the submission
that is cut before the client observes a terminal; it is never modeled as a
second operation after a visible terminal. The runner rejects a disconnect for
an identity whose terminal was already observed. It checks canonical SSE, visible
response category, stage outcome, artifact and action identity, persistence and
reload state, typed recovery, route budgets, terminal fingerprints, stale
actions, and orphan-turn reconciliation.

Each trajectory currently carries one exact owning issue and a narrow set of
step-scoped allowed failure masks. The approved #229 contract now owns the exact
reliability vocabulary: `confirmation_id` is the Run `action_identity`, its
`Idempotency-Key` must match, and ambiguous Run responses reconcile through the
owner-scoped by-action lookup before a `404` may permit one exact replay. Ordinary
turns project approved lifecycle states; an unreconciled stale turn becomes
terminal `abandoned` recovery with `turn_abandoned` and a `retry_last_turn`
action keyed by `request_message_id`. Keep the tags until the corresponding
runtime lane lands and the full trajectory passes. The mocked mechanics do not
replace the sanctioned live gate, deployed exact-SHA browser proof, or founder
approval.

## Categories

This slice covers the locked built-surface categories present in the fixtures.
Categories for unbuilt surfaces, including comparison, freshness on return, and
research-to-test, get added when their lanes land.

## Prose Judge

Judge rubric version: `argus-prose-quality-v1`.

The judge grades prose only: recovery tone, honesty, Spanish language integrity,
and raw runtime error leakage. Typed facts such as intent, assets, dates,
benchmark, stage outcomes, and capability verdict are asserted outside the judge.
