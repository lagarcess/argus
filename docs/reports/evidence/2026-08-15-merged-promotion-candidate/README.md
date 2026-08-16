# Merged promotion candidate, live eval at c2dbddd7

Measured 2026-08-15 after PRs #510, #511, #507, #514 landed together.

| run | result |
|---|---|
| baseline `eaf5d52b` | 43 passed / 17 failed |
| PR #514 alone, `9409599a` | 53 passed / 7 failed |
| **merged `c2dbddd7`** | **46 passed / 14 failed** |

Zero regressions against the baseline, so the promotion gate is satisfied.

Eight of #514's ten wins did not survive the merge: all five
`asset_discovery_*` cases, both `graceful_recovery_*_weekly_options_aapl`
cases, and `dca_capital_semantics_zero_contribution_names_buy_and_hold`.
Those were fixed by prompt guidance alone, which is why they flip.

`.agent/interpreter_prompt_fingerprint.json` records `last_measured` at
`9409599a` (53/7). That is accurate for the commit it names, but it is not
the state of this tree. **Any lane comparing against integration must use
the 46/14 scorecard here**, not the fingerprint's.

Cost: $1.31, 27 minutes, 60 cases.
