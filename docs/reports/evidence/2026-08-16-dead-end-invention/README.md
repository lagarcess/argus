# Never dead-end, never invent: measurement evidence

Lane base `811dcbcb`, reconciled one-way with integration `7707f6ab`.
Candidate `577099f6`. Baseline for comparison:
`docs/reports/evidence/2026-08-16-main-promotion/live-eval-scorecard.json`,
**58 passed / 2 failed**.

These supersede the runs taken at `bdb4529a` and `628747ce`. Both earlier pairs
are invalid as evidence for two separate reasons, recorded here rather than
quietly replaced.

## Why the earlier scorecards do not count

The review found both `offered` gates were reading the wrong thing.
`recovery_option_ids` looked for `options` inside `payload` where the runtime
writes it as a sibling, so it was empty in all 60 blocks of every earlier run.
`named_unavailable` read the sidecar's ungated drop list rather than the reply,
so the trending-crypto case passed a naming assertion on this text:

> Here are the trending cryptos I can help you test.

Replaying the corrected projection over that exact record:

```
before: named_unavailable = ["peaq","Wiki Cat","Venice Token","Bitcoin"]  -> passed
after : named_unavailable = [], dropped_not_named = [...]                -> fails
```

**This retracts a claim made in the previous round.** I reported that 8 of 9
strengthened cases passing on base was draw dependence. It was not. The
assertion never measured the prose, so the base run said nothing about it.

## Live runs, both at `577099f6`

| run | passed | failed | failures |
| --- | --- | --- | --- |
| 1 | 59 | 1 | `asset_discovery_trending_crypto_exact_issue_344` (`offered.names_unavailable`) |
| 2 | 58 | 2 | the same case, plus `asset_discovery_semantic_pharma_escalation_issue_344` (`prose_judge:honesty`) |

The trending-crypto failure **reproduces in both runs**. It is not variance, and
it is the newly-live assertion catching a real gap rather than a regression:
on a turn that offers rows, the composer passes drop names through
`_user_subject_drops`, which mentions a dropped name only if the user's own
message echoed it. So a "find me trending cryptos" reply offers three rows and
says nothing about dropping Bitcoin.

**This is an open product decision, deliberately not resolved here.** Naming
those drops collides with an existing contract, `TestDropDisclosures`:
"absences the user can see are explained; internal filtering is silent", pinned
by `test_pipeline_only_drops_stay_silent`. I tried the change, it turned that
test red, and I reverted rather than flip an existing assertion unilaterally.
The two coherent options are:

1. Name search-surfaced drops on the success path too, on the grounds that a
   name the search returned under the category the user asked for is the user's
   subject by construction. This retires `test_pipeline_only_drops_stay_silent`.
2. Require `names_unavailable` only when nothing actionable was offered, which
   is the founder-facing symptom, and leave the silence contract intact.

## What is demonstrated, not read

Finding 1, the rail override, executed against the real `_dispatch` with a
typed `unsupported_request` carrying AAPL, the user's window, and no constraint
payload:

```
company_lookup / live_quote / cross_company / etf_constituents /
market_pulse / sector_radar / screening / market_stats / current_external
  -> dispatch returns None for every kind
allowance exhausted -> None (exhausted_result never reaches the stats answerer)
```

The browser could not force this draw: every live options turn had the
interpreter emit `unsupported_constraints`, so the upstream veto caught it
first. That is precisely why the gap was invisible to the previous round's
browser evidence.

Finding 2, one priceability owner, on live providers:

```
PENGU -> no_history      WLD -> no_history
AAPL  -> tradable        SOL -> tradable
verified_peers offered: ['AAPL']
```

## Browser acceptance at this head

Forced all-unpriceable set, the case that started this lane:

> Catecoin, 牛来, and Z500 appeared in the search but could not be confirmed as
> tradable assets here; Captain TRON and World Water Reserve also appeared but
> the match with what you intended is uncertain. To proceed, please request a
> different category or provide a specific symbol or company name to test.

Trending cryptos, 5 draws including Spanish: **5/5 offered actionable rows**
(HYPE/USD, SOL/USD, Dogecoin, 2-3 rows per draw). The tightened corroboration
cost no rows, because those turns carry `asset_class_hint="crypto"`.

Weekly options, 5 draws: **0 fabricated readouts**, limit named 5/5, asset and
window kept in the rendered prose 3/5 (the other two carry them in the typed
options). Chips rendered in 4/5. The dangling "Which of these" with no options,
seen once last round, did not recur.

## Model-facing text

`tests/test_interpreter_prompt_freeze.py` passes unchanged; no edit in this lane
is inside the fingerprinted surface. That remains a finding in itself:
`discovery/composer.py` builds its voicing prompts as plain `{"role": "system"}`
dicts inside functions whose names do not match the measured suffixes, so the
Standard 12 gate cannot see text that steers every discovery turn.
