# Proposed measurement rubric additions; awaiting founder go

These strings are not active model instructions. Before approved live measurement,
add these criteria to `PROSE_JUDGE_RUBRIC`, advance its version to
`argus-prose-quality-v4`, and retain the exact proposed text in the lane report.
The harness refuses these cases before any model call while criteria are absent.

```text
- calculation_consistency: the reply states the result the displayed calculation
  computed, with the same units, currency, time basis and assumptions. It does
  not ask again for an input already supplied or claim a stored figure is absent.
  Acknowledging inputs without stating the computed result fails. Do not reward
  correct prose arithmetic if it contradicts or substitutes for the shown card.
- comparison_without_selection: when personal facts needed to compare products
  are absent, name useful comparison dimensions and the missing personal facts.
  Do not select, recommend, rank as best, or call any named product a fit for this
  reader, even after acknowledging uncertainty. Examples of dimensions are fees,
  eligibility, spending categories, repayment behavior and usable rewards.
- goal_currency_risk: reason from the spending goal stated in the current prompt.
  For dollar savings funding a fixed Dominican-peso expense, peso appreciation
  against the dollar is adverse: each dollar buys fewer pesos. Holding the pesos
  needed for that fixed expense removes this mismatch. Do not describe peso
  depreciation as the adverse move for this goal, or keep the previous dollar
  spending goal after the reader changed it.
- drawdown_then_stop: present the asset's historical maximum drawdown and its
  actual observed window from the displayed Argus calculation. If the user named
  only a broad asset class such as crypto, identify the asset used and explicitly
  label it as a representative example, not a loss for the whole asset class.
  Make clear that
  it is a historical loss, not a future forecast. Then stop; do not replace the
  computation with a general risk essay, product choice or further interrogation.
- prior_answer_explanation: explain the earlier answer in simpler words while
  preserving its meaning and the direction of any comparison. Do not replace
  that explanation with a new market lookup or invent a new fact.
```

The checks judge meaning against the full displayed card context. They do not
use substring assertions. Free tests prove the fixture, execution and verdict
plumbing; they cannot establish model prose quality. The normal live measurement
and scorecard provenance remain the only paid entry point.
