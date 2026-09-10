# Result readout validator dispositions

Both composers now return one complete `text` field. The shared owner is
`src/argus/domain/result_readout_grounding.py`; the run owns every metric and
the retained engine configuration owns execution inputs. Stored charts are
optional. Sampled trade markers are not treated as a complete trade ledger.

| Check or former rule | Disposition and reason |
| --- | --- |
| `_false_figure` | Keep: catches a quoted number absent from compatible stored metrics, execution inputs, dates, optional chart, or the explicit starting-capital drawdown illustration; currency, percentages/points, ratios and counts remain distinct, with tolerance determined by the quoted precision and compact/scientific scale. |
| Ratio presentation | Keep inside the figure check: `win_rate` and `observed_ratio` may be printed as percentages; other numbers are never indiscriminately multiplied by 100. |
| `_contradicting_comparison` | Keep: catches visible English/Spanish beat, lag or match claims that contradict canonical benchmark comparison; one role matcher identifies ticker and generic benchmark subjects in both clause selection and negated/inverted claims; a shared strategy/benchmark ticker requires an explicit role on either side. |
| `_internal_field_name` | Keep: catches visible snake-case keys, supplied camelCase keys, quoted schema fields, draft schema names, and internal fact/context/receipt terminology. |
| `QuickTakeDraft.relative_performance_claim` self-report | Remove: model metadata is not visible truth; the shared check reads the complete visible draft instead. |
| `_quick_take_mentions_unknown_metric_number` three-figure allowlist | Remove: rejects honest stored annualized return, risk, costs and activity; the shared numeric check accepts all stored metrics. |
| `_contains_unknown_breakdown_metric_number` limited metric allowlist | Remove: duplicates the Quick take validator and excludes honest richer figures; both surfaces now use the shared check. |
| `_quick_take_mentions_required_visible_facts` / `_mentions_benchmark_comparison` | Remove: forces benchmark wording and figures already available on the card; omission alone is not a false statement. |
| `_rendered_breakdown_mentions_required_facts` / symbol and date mention helpers | Remove: forces repetition of setup and identity; omission alone is not a false statement. |
| `_required_quick_take_fact_ids` / `_required_result_breakdown_fact_ids` | Remove: mandatory fact IDs force content and do not prove visible correctness. |
| Breakdown fact-ID membership and coverage checks | Remove: unused self-reported metadata cannot establish that the prose is true. |
| `_quick_take_mentions_signed_benchmark_delta` | Remove: a correctly signed historical difference can be honest; rejecting its notation is a style restriction. |
| `_next_check_kinds_are_supported` / next-experiment draft fields | Remove: follow-up actions already own next experiments and the Quick take does not render these fields. |
| Quick take required takeaway/tested/optional bullet schema | Remove: forces an outline; a complete model-written text field lets the model explain the result naturally. |
| Quick take language-quality self-audit and optional-bullet salvage | Remove: self-report is not language proof and salvage could expose a partial; generation language is instructed and the new transport stamps it for the reader's language gate. |
| Breakdown 1–3 block schema / 220-word instruction / 520-word rejection | Remove: these cap content; the prompt assigns a deeper, concise role without rejecting an honest draft for length. |
| `_contains_disallowed_breakdown_heading` | Remove: heading choice is a formatting rule; the prompt keeps titles with the unchanged UI frames. |
| Provider-name substring blacklist | Remove: a provider name alone is not a false figure or schema leak; actual internal keys and schema names remain rejected. |
| Fact-ID HTML-comment extraction | Remove: there is no grounding metadata to salvage or strip from visible prose. |
| Empty/malformed response and model/timeout failure handling | Keep as completion boundaries: unavailable complete text falls back and never exposes a partial response. |
| Em-dash handling | Normalize punctuation after complete-text validation; no extra content rejection or partial salvage is introduced. |

The prompt additionally assigns historical, non-advisory interpretation to
both surfaces, prohibits price-cause claims and forecasts, and makes Breakdown
use the accepted prior Quick take as context. These are measured writing
requirements, not another language classifier or a content quota.

Numeric validation folds accents internally without changing visible text and binds count labels locally so dates do not inherit distant trade labels. Explicit incompatible units and false rounding remain rejected.

The figure checker verifies numeric membership and rounding, not arbitrary
natural-language semantic entailment. The benchmark check covers explicit
comparison wording. Targeted live measurement remains required for quality,
language, surface distinction, and the prompt fingerprint.

## Deterministic development evidence

Python 3.10.20. Provider keys were blanked for every command; no live model
calls were made. These checks cover the working tree, not a release SHA.

- Initial new generation tests: 17 failed / 18 passed because the current
  composer rejected complete `text` drafts and omitted stored chart/context.
- Decimal/ratio cases: 4 failed / 2 passed before the precision and typed
  percentage handling; configuration precedence: 1 failed / 1 passed before
  preserving the engine-owned capital over stale descriptive parameters.
- Malformed numeric draft: Breakdown raised `ValueError` before the shared
  parser safely rejected it; final check returns no draft.
- Full affected suites passed: 239 tests across
  `tests/test_model_result_readouts.py`,
  `tests/agent_runtime/test_execute_recovery.py`,
  `tests/test_openrouter_policy.py`,
  `tests/test_benchmark_comparison_language.py`, and
  `tests/test_render_workflow_execution.py`, with `pytest -q --no-cov`.
- A final spaced-em-dash regression failed for both surfaces before punctuation
  normalization was tightened. The complete 51-case model readout suite then
  passed, with `ruff check` passing for all changed Python files.

The shell environment for verification was
`OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture`.

Review delta: the unit-mixing, generic benchmark-subject, and compact/scientific
number regressions produced 40 failed / 14 passed before the fix. After the
shared checker fix, all 105 model-readout cases and all 295 tests across the
five affected suites passed; Ruff passed. Prompt text and schema were unchanged.
