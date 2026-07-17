# Argus Eval Harness

This folder contains the private-alpha measurement eval harness. Cases live as
data fixtures, and the harness asserts typed runtime outcomes instead of exact
assistant phrasing.

## Test Tiers

- **Mocked harness - every change (free, no API calls):**
  `poetry run pytest tests/evals/test_measurement_eval_harness.py`
  Validates routing, state, and contract logic. This is the everyday inner-loop
  check.
- **Live eval - only the 3 sanctioned moments:**
  1. Pre-merge on a PR that changes runtime behavior.
  2. Main promotion candidate.
  3. After any model/provider change.
- **Browser QA is also real-API:** every turn spends tokens. Use it at gates, not
  per hypothesis.

## Mocked Run

Run the mocked harness checks with:

```bash
poetry run pytest tests/evals/test_measurement_eval_harness.py -q
```

This run is free. It does not call the LLM, does not spend provider tokens, and
is safe to run anywhere.

## Search Provider Evaluation (Issue #244)

Run the bounded Search provider contract with:

```bash
poetry run pytest tests/evals/test_search_provider_eval.py -q --no-cov
```

This evaluation is also free. It replays clearly labeled synthetic
provider-shaped Perplexity-direct and OpenRouter web-search fixtures against a
shared rubric. It does not make network or provider calls and therefore cannot
prove real relevance, citation quality, or latency.

Generate the non-versioned decision evidence with:

```bash
poetry run python -m tests.evals.search_provider_eval
```

The report is written to
`temp/issue-244-search-provider-evaluation.json`. It must recommend deferral
until real provider evidence, issue #241 integration, and explicit founder
activation exist. Any public citation/context schema also remains behind its
separate API-contract approval gate.

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

`temp/` is gitignored, so scorecards are local run artifacts. Each scorecard
includes per-category totals and pass rates. Expected-fail cases never count as
passes; they are reported separately so known broken behavior stays visible.

## Expected-Fail Cases

An expected-fail case must be tagged with an issue number and scoped
`allowed_failures`. The expected-fail tag only masks failures with those allowed
prefixes; any unrelated failure still fails the eval.

The lane that fixes the tagged issue must flip the case to pass as part of that
lane's acceptance. Expected-fail is a truthful baseline, not a permanent waiver.

## Categories

This slice covers the locked built-surface categories present in the fixtures.
Categories for unbuilt surfaces, including comparison, freshness on return, and
research-to-test, get added when their lanes land.

## Prose Judge

Judge rubric version: `argus-prose-quality-v1`.

The judge grades prose only: recovery tone, honesty, Spanish language integrity,
and raw runtime error leakage. Typed facts such as intent, assets, dates,
benchmark, stage outcomes, and capability verdict are asserted outside the judge.
