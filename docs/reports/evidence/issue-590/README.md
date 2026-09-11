# #590: what to try next after a result

Issue #590: after a completed backtest, "ok what should I try next?" returned
the retry message `latest_result_followup_unavailable` and no suggestions, in
production (`ee9c3491`) and on integration (`4482aaa6`). The follow-up composer
rejects next-experiment prose by design (retired in `72d2fe3a`, the
`argus_next_experiments` rows own that surface), and neither follow-up path
attached the rows. The measurement case
`asset_discovery_not_result_followup_issue_244` failed on
`offered.min_next_experiment_rows` in every live run since the check arrived.

Lane branch `claude/result-followup-next-experiments-383492`, base integration
`46d43c1d`, PR #592. Code head `67067751` (`3cc37cfd` plus the Codex round 1
fix); the commits after it are evidence only.

## What changed

- `src/argus/agent_runtime/result_followup_answers.py` (new): the three shapes
  a latest-result follow-up answer takes. `next_experiment_followup_patch`
  answers a `next_experiment` focus with the rows `next_experiments_sidecar`
  builds from the latest result's metadata, the one owner of the rows, plus a
  one-sentence lead-in in the workspace language; `composed_result_followup_patch`
  wraps composer prose in its typed heading; `unavailable_result_followup_patch`
  is the retryable recovery, which never wears result chrome.
- `src/argus/agent_runtime/stages/interpret_actions.py` and
  `src/argus/agent_runtime/stages/interpret.py`: both follow-up paths (and the
  interpreter-unavailable path) build their patch from those helpers. A
  `next_experiment` focus never calls the composer; the recovery appears only
  when no row can be built.
- `src/argus/agent_runtime/next_experiments.py`: the lead-in copy (`en`,
  `es-419`) lives beside the send templates, and the module resolves its locale
  through `runtime_locale` instead of its own inline rule.
- `src/argus/agent_runtime/result_followups.py`: the engine metric paths the
  fact bank reads (`delta_vs_benchmark_pct`, `max_drawdown_pct`) are shared
  constants, so the rows' `why` reason and the fact bank quote the same figures.
- `docs/API_CONTRACT.md`: the Try next section documents the follow-up answer.
- Codex round 1 (P1, fixed in `67067751`): the follow-up message has no result
  card, so its `change_date_range` and `compare_buy_and_hold` rows had no run
  to anchor on and a tap would have sent their label as prose. The sidecar now
  names its run as `source_run_id` (the latest result reference's id, the same
  identity `latest_run_id_for_action` falls back to); the web client reads it
  on hydration and on the streamed final payload and falls back to it when the
  message has no card, so those rows submit the contract's `refine_strategy`
  action with `run_id` and `next_experiment_kind`. Knowledge-answer rows also
  ride a card-less message but belong to no run; their prose turn is the
  contract's path and they are unchanged.

Decisions worth knowing:

- An explicit ask gets the result's full offer. Spec
  `2026-07-29-try-next-surface-ownership.md` §4.3 (non-repetition) restrains
  unsolicited re-offers; applying it to a question would answer "what should
  I try next?" with the one kind the first explanation left out, or with the
  recovery once every kind had been offered.
- The rows answer carries no `response_intent` heading: the Try next section
  label is the heading, and the follow-up chrome would print it twice.
- No model-facing text changed. `tests/test_interpreter_prompt_freeze.py`
  passes with `.agent/interpreter_prompt_fingerprint.json` untouched.

## Proof

### Focused tests

`tests/agent_runtime/test_result_followup_answers.py`: the helpers, both stage
paths called directly for buy and hold, DCA and indicator results in `en` and
`es-419` (the composer is a stub that fails the test if called), the
recovery-only-when-no-rows case on both paths, and the production repro as a
full `run_agent_turn` in both languages with the first explanation's offer
already on record. Three existing tests whose premise was the dead end were
re-pointed: the two chrome tests in `test_latest_result_fact_answers.py` now
use a composed focus, and the focus-preservation test in
`test_interpret_stage.py` asserts the rows answer.

Hermetic sweep at `3cc37cfd`: `tests/agent_runtime tests/test_spine_guardrails.py`
2227 passed; the mocked eval suite from `tests/evals/README.md` 257 passed;
`scripts/check_modularity_budget.py` no violations.

### The measurement case, live

`drivers/run_case.py` runs one case through the harness with both provider
modes assigned outright (the integration `.env` pins synthetic market data and
leaves the asset mode empty; `setdefault` after `load_dotenv` keeps that).

| Run | Record | Status | Rows | Billed |
| --- | --- | --- | --- | ---: |
| 1 at `3cc37cfd` | `live/single-case-3cc37cfd.json` | failed: `offered.min_next_experiment_rows` | none | $0.0022 |
| rerun at `3cc37cfd` | `live/single-case-3cc37cfd-rerun.json` | passed | `change_date_range`, `same_setup_peer_asset`, `recurring_monthly_buys` | $0.0162 |

Run 1 did not reach the fixed path: the structured tier timed out on the
primary model and the fallback's read failed validation, so the turn carried
no typed focus and went through the interpreter-unavailable path, whose
general-focus composer draft was rejected. That is an availability failure,
and `tests/evals/README.md` allows one rerun of a surprising failure. The rerun
typed the turn `next_experiment` and answered with three rows, no recovery and
no composer receipt.

### Browser demo at the code head `67067751`

`drivers/serve.py` serves this tree on 8590 (memory persistence, mock auth,
real interpreter, live market data and asset provider); the web dev server on
3590 ran with `NEXT_PUBLIC_MOCK_AUTH=true` and `NEXT_PUBLIC_ENABLE_SPANISH=true`.
`drivers/browser_demo.mjs` drives the production repro in the real app, once per
language: the Apple 2024 question, Run backtest from the confirmation card, the
what-next follow-up, then a tap on the date-range row of the follow-up message
while recording the request the client sends. `browser/report.json` records the
rows, the captured request, timings and page errors (none).

| Language | Follow-up answer | Rows | Recovery | Follow-up turn |
| --- | --- | --- | --- | ---: |
| `en` | Here is what you can try next from this result. | Try monthly recurring buys (Worst drop was -15.5%), Try a supported SMA/EMA crossover, Test a different date range | no | 21.6 s |
| `es-419` | Esto es lo que puedes probar después a partir de este resultado. | Probar compras mensuales recurrentes (La peor caída fue -15.5%), Probar un cruce SMA/EMA compatible, Probar otro rango de fechas | no | 37.4 s |

The date-range row tapped from the follow-up message sent
`{"type": "refine_strategy", "presentation": "result", "payload": {"run_id":
<the run's id>, "next_experiment_kind": "change_date_range"}}` in both
languages, and Argus answered with the date-only clarification anchored on the
run ("What period would you like to test instead?" / "¿Qué período te gustaría
probar?"). That is the Codex round 1 finding closed in the real app.

Screenshots: `browser/<language>-1-confirmation-1280.png`,
`-2-result-1280.png`, `-3-what-next-1280.png`, `-3-what-next-390.png`,
`-4-date-row-1280.png`. The rows lead with the drawdown reason because the real
run's worst drop (-15.5%) crosses the sidecar's deep-drawdown threshold, read
from the same persisted metrics the fact bank quotes.

Billed, from the API's route receipts: $0.16 for the two conversations at this
head, plus $0.02 for an attempt at the same head that the structured tier's
outage sent down the interpreter-unavailable path (below), plus $0.19 for the
runs at `3cc37cfd` (two conversations and one attempt aborted by a driver bug:
it matched `innerText`, which carries the CSS uppercase of the section labels).

### Observed beside the fix: the structured tier's outage path

Two of the six live what-next turns driven for this lane never carried a typed
focus: the primary interpreter model timed out (12 to 20 s) and the fallback
model's read failed local validation, so the turn went through the
interpreter-unavailable path. That path composes a general-focus answer; in
the browser it produced a "What happened" prose answer that listed the same
options as bullets (no rows, no recovery), and in the harness its draft was
rejected and the recovery appeared. Neither is the dead end #590 describes,
and both are outside this lane: with no typed focus there is no honest way to
attach rows without a phrase gate before interpretation. It is recorded here
because it decides whether the measurement case passes on a given run.

### Full live measurement

Pending: run once on the final head after review, compared case by case
against the scorecard named in `.agent/interpreter_prompt_fingerprint.json`
with `drivers/compare_baseline.py`. This section is updated when it lands.

## Spend

| Step | Billed |
| --- | ---: |
| Measurement case, run 1 and rerun (`3cc37cfd`) | $0.02 |
| Browser demo at `3cc37cfd`, including the aborted attempt | $0.19 |
| Browser demo at `67067751`, including the outage-path attempt | $0.18 |
| **Total so far** | **$0.39** |

## Reproduce

```bash
# One measurement case, live (paid)
I590_TREE="$PWD" I590_ENV_FILE=<env file> poetry run python \
  docs/reports/evidence/issue-590/drivers/run_case.py <label> <out.json> \
  asset_discovery_not_result_followup_issue_244

# Local live API for the browser demo (paid per turn)
I590_TREE="$PWD" I590_ENV_FILE=<env file> poetry run python \
  docs/reports/evidence/issue-590/drivers/serve.py
cd web && NEXT_PUBLIC_ARGUS_API_URL=http://127.0.0.1:8590/api/v1 \
  NEXT_PUBLIC_MOCK_AUTH=true NEXT_PUBLIC_ENABLE_SPANISH=true \
  NEXT_PUBLIC_RESEARCH_RAIL_ENABLED=true bun run dev -- --port 3590
I590_TREE="$PWD" node docs/reports/evidence/issue-590/drivers/browser_demo.mjs

# Full live measurement on a clean, committed head (paid)
I590_ENV_FILE=<env file> bash docs/reports/evidence/issue-590/drivers/run_measurement.sh
```

The env file is read, never written. Both provider modes are assigned in the
process environment by every driver; do not rely on `setdefault`.
