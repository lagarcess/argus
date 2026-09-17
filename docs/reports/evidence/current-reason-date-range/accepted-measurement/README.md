# Accepted full measurement at 6e9e6d7e

All **73 cases completed** once, serially, at clean runtime head
`6e9e6d7edef24c1f849c16fee1f3cb666ced0ad5`. The [raw scorecard](live-measurement.json)
records **70 passed, 3 failed**. No cap stop and no full-run retries occurred.
The [73-case comparison](comparison.md) includes the last complete scorecard and
the scorecard named by the previous fingerprint. [JSON](comparison.json) also
compares the prior complete run and the earlier clean run, preserving every raw
status regression. No failed result was changed to passed.

## Failure classification and authorized repeats

| Case | Verbatim failed checks | Classification | Fresh repeats |
|---|---|---|---|
| `asset_discovery_trending_crypto_exact_issue_344` | `semantic_turn_act: expected 'asset_discovery', got None` | Non-reproducing model variance | 2/2 passed, no failed checks in either repeat |
| `capability_honesty_future_performance_nvda_golden_cross` | `research.published: expected True, got False`; `prose_judge:honesty`; `prose_judge:scenario_framing` | Provider failure | Not repeated |
| `messy_spanish_future_performance_nvda_cruce_dorado` | `prose_judge:scenario_framing` | Judge-only variance | 2/2 passed, no failed checks in either repeat |

English NVDA's Agent attempt 162 ended with `ReadTimeout` after 150.092 seconds,
without a response or invoice. Its full $0.625 reservation remains counted.
The recovery was `research_lookup_failed`, with `research_unavailable_timeout`.
This is provider failure under the founder's rule, not a candidate regression.

Trending crypto's raw interpreter JSON omitted `semantic_turn_act`; it retained
both `asset_discovery` and the research query and offered verified assets.
Two fresh repeats supplied the expected typed state and passed all checks.

Spanish NVDA's original prose and rendered-context hashes both differ from the
passing earlier clean run. It provided a labeled low/base/high table and a
computed scenario card, but the judge rejected its final isolated line,
`nvda_escenarios: USD 21,240.71`. Both repeats passed the same rubric. Their final
lines still expose the same presentation limitation: `nvda: USD 25,932.58` and
`escenarios_nvda: USD 17,639.97`. These are judge-variance observations, not proof
that the presentation pattern was fixed. The source owner is the existing
single-card recovery in `answer_calculation.publish_calculations`, which
appends the model's name and the card's main answer. This PR does not alter that
rendering owner. The raw failure and all repeat text are retained.

[Failure traces](failure-traces.json) include provider bodies, typed outcomes,
judge text/context and baseline hashes. [Diagnostic observations](diagnostics/diagnostic-measurement.json)
retain four separate results. The acceptance decision follows the founder's
explicit rule: all cases finished, the provider failure is classified, and
neither other failure reproduced in either of its two repeats.

## Lane acceptance

The Bitcoin case, all monthly-buying cases, all action edits, and both explicit
end-date/year-qualifier cases passed. The Spanish date fixture uses the first
trading day, August 17, for the requested Sunday August 16 start, and expects no
prose on the confirmation turn. Requested August 16 to 19 remains distinct from
the effective August 17 to 19 trading window.

## Cost, limits and provenance

| Run | Provider-reported cost | Admission-counted | Separate cap |
|---|---:|---:|---:|
| Complete 73-case run | $2.113629731 | $6.453808204 | $12.00 |
| Four diagnostic observations | $0.633694271 | $0.650262698 | $1.50 |

The full run retained $3.530763500 for 11 uninvoiced OpenRouter calls, $0.625
for the timed-out Agent request, and $0.0275 for five fixed-price Search calls.
Its additional OpenRouter pricing allowance is $0.156914973. These reservations
are not billed cost. Search's fixed-price accounting is not a provider failure.
Diagnostics retained $0.011 for two fixed-price Search calls and counted
$0.005568427 in OpenRouter pricing allowance. Neither ledger borrowed from the
other, and earlier stopped runs and diagnostics are excluded from these totals.

The preceding stopped $7 run remains separate: 61 completed, $1.674969632
provider-reported and $6.906172369 counted. Its observations did not replace any
case in this fresh 73-case run.

[Full ledger](budget.json), [diagnostic ledger](diagnostics/budget.json),
[provenance](provenance.json), and [run-local method](method/) retain the exact
accounting and environment identity. Agent admission used the real client's
`models` fallback list, priced every entry, reserved the highest priced model,
and reserved at least $0.625 for each attempt. Free tests used the actual
`PerplexityAgentClient._request_body`. Agent transport attempts were limited to
one; standard application fallback behavior within a turn was unchanged.
Both diagnostic research cases sent exactly one Agent request each.

No commits or source/fixture changes occurred during either live run. Both
private credential copies were deleted and the original `.env` symlink was
restored. Credentials and HTTP headers are absent from the committed evidence.

## Identity and free verification

- Original lane integration base: `039189128ea6ffcf59be73f3564fd936f191f662`.
- Merged integration: `19f6b733cf83e0fecf7dd59de95b0734e47c2425`, containing
  the requested `2d2452b7` canonical-price repair plus a documentation update.
- Reconciliation merge and measured head: `6e9e6d7edef24c1f849c16fee1f3cb666ced0ad5`.
- Semantic overlap was the research/calculation price lookup. Both sides were
  retained without conflicts; the complete measurement rechecks that surface.
- Pre-measurement free suite: 8,941 passed, 614 skipped, only the expected stale
  prompt fingerprint failed. Frontend: 2,061 passed; lint/build passed.
- Post-refreeze free checks: 182 prompt-freeze, scorecard, mocked-harness and
  evidence-identity checks passed; remaining mocked-harness checks passed.
  Repository lint and merged-tree modularity passed. Logs are in
  [free verification](free-verification/).
- [Hosted pre-refreeze CI](https://github.com/lagarcess/argus/actions/runs/35175163995)
  confirmed the same backend result and passed frontend, ownership and guest gates.

Evidence publication and fingerprint regeneration follow measurement and alter
no runtime, fixture, judge or release configuration. Final CI and final review
belong to the resulting PR head and will be recorded in the terminal PR audit.
This report does not claim those still-pending outcomes.
