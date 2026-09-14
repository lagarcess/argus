# Live measurement at dc8608c8

The full live measurement ran once on dc8608c8, the head that merges
codex/private-alpha-next (e208d10a), with both provider modes set to
live_provider. `live-measurement.json` is its scorecard.
`measurement-comparison.json` compares it case by case with the scorecard the
interpreter fingerprint named (conversation-after-result/final-measurement,
36086097). `measurement-retries.json` holds the one single-case retry.

## Result

69 passed, 2 failed, 0 infrastructure errors, against the baseline's 64, 7 and 0.

- Improved: six cases. Five DCA capital semantics cases, most likely from the
  merged issue 600 focused-repair fixes, and the golden cross control on AAPL.
- Failed in both: `capability_honesty_future_performance_nvda_golden_cross`. The
  interpreter reads the golden cross as a backtest and asks for clarification,
  in the baseline and here.
- Failed once, passed on retry: `messy_spanish_future_performance_nvda_cruce_dorado`.
  Its research call returned HTTP 500, the run's only provider error, so no
  research answer was published and the judge failed its scenario framing.
  Rerun alone at dc8608c8 it passed with a published research answer and
  labeled scenarios from cited inputs.

## The three concept cases

All three `ordinary_conversation_concept` cases passed with a published balanced
research answer. By run order against the route log lines, compound interest
was routed as a concept question (`research_answers_concept_question`), and
inflation and ETF, which the interpreter left with no question kind, through
`research_answers_unkinded_question`.

## Spend

The scorecard reports only OpenRouter route receipts: $1.4885 over 345 priced
receipts, 13 unpriced. The run's research provider calls were billed but are not
priced here: 5 balanced (one of them the HTTP 500), 1 fast and 9 find searches,
plus the retry's balanced call. The lane ledger records them as estimates, about
$0.96 to $1.87 in all.
