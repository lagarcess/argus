# Parked registry interpreter rewrite

Historical evidence for roadmap decision 9. The unfinished rewrite is preserved
on `codex/registry-interpreter-rewrite` at
[`dcde9affb92abd16488310ac44e91ef9d5f7c6dc`](https://github.com/lagarcess/argus/commit/dcde9affb92abd16488310ac44e91ef9d5f7c6dc).
The [commit manifest](https://github.com/lagarcess/argus/blob/dcde9affb92abd16488310ac44e91ef9d5f7c6dc/docs/reports/registry-interpreter-rewrite-snapshots/worktrees.json)
retains the parallel unfinished variants. None of these measurements accepts a
fingerprint or establishes readiness for the declaration-only lane.

The experiment rewrote the interpreter's response contract, generating a new
system prompt and tool catalog. In `llm_interpreter_types.py`, field descriptions fell
from 40 at `542fcfb2` to 19 at `31b20baf`. Seven historical intents became
`calculate`, `explain`, `follow_up`, and `cannot`; the model could select arbitrary
declared calls, including none, multiple tools, or repeated use of one tool.
All four canonical intents were observed; structural tests separately covered
composition and repetition. These observations did not establish behavioral parity.

| Full run | Exact measured head | Native pass / fail | Accounted or estimated USD |
| --- | --- | ---: | ---: |
| [Initial](https://github.com/lagarcess/argus/blob/dcde9affb92abd16488310ac44e91ef9d5f7c6dc/docs/reports/evidence/registry/live-gate-initial.md) | `3c4f5aab93f1928d999a20fc34c4b0a6bcecf5a8` | 43 / 25 | $1.80362615144 |
| [Second](https://github.com/lagarcess/argus/blob/dcde9affb92abd16488310ac44e91ef9d5f7c6dc/docs/reports/evidence/registry/live-gate-second.md) | `d5ad4b6e1c3e475820a33fa1d55f4f6f1658e467` | 52 / 16 | $2.04259523952 |
| [Third](https://github.com/lagarcess/argus/blob/dcde9affb92abd16488310ac44e91ef9d5f7c6dc/docs/reports/evidence/registry/live-gate-third.md) | `72aa04a06d00a76421414e778d67fc2cf3ccd0f2` | 49 / 19 | $2.737909816178 |
| [Fourth](https://github.com/lagarcess/argus/blob/dcde9affb92abd16488310ac44e91ef9d5f7c6dc/docs/reports/evidence/registry/live-gate-fourth.md) | `c6c28fefe5b30c1f5d0a67656dc9c6fa025a44e2` | 58 / 11 | $2.998189005568 |

The first three suites had 68 cases; the fourth had 69. All completed without
infrastructure errors or skips. Together, $9.582320212706 was reported or
estimated, with additional charges unknown. Unpriced receipt counts were
16, 10, 24, and 17; receipt rows are not distinct requests. The first three
include estimated Search charges and provider-reported Research Agent invoices
with tariff mismatches. They are not complete validated bills. Four earlier
retrieval-schema recaptures cost another $0.52122, outside this table.

Initial failures exposed lost dates, money roles, costs, unsupported limits,
and recovery when declared inputs bypassed preparation, alongside observation
changes. The second retained date/money omissions, cost-grounding loss, Spanish
BTC classification, discovery, and follow-up failures. The third added failures
around capital edits, benchmarks, bilingual DCA, and selection evidence.
Source and grader changes prevent attributing every transition to the catalog.

The fourth had **ten pass-to-fail transitions against each older fingerprint**.
Against 565: Spanish category discovery; English comparison anchor; recent IPO;
trending crypto; AAPL news-sentiment rules; DCA budget ceiling; bare-amount chip;
Spanish-pesos chip; ETH default benchmark; modeled costs. Against 411,
result-followup discovery replaces the Spanish-pesos chip. The
[complete case/check comparison](https://github.com/lagarcess/argus/blob/dcde9affb92abd16488310ac44e91ef9d5f7c6dc/docs/reports/evidence/registry/verification/c6c28fef/measurement-analysis/comparison.json)
preserves exact IDs and both sets.

The separate [56-probe interleaved comparison](https://github.com/lagarcess/argus/blob/dcde9affb92abd16488310ac44e91ef9d5f7c6dc/docs/reports/registry-interpreter-rewrite-snapshots/archived-analysis/analysis.json)
tested 14 inputs twice per arm: baseline
`542fcfb2432e906663160d8cb874d955faeafd16` recorded **25/3**; candidate
`31b20baf7a036fdd9148bce8a90a838e076be201` recorded **15/13**. All 56 outputs
are complete; matching inputs do not mean matching native grading contracts.
Candidate `33-candidate-r2` and `44-candidate-r2` are invalid apparent passes:
the judge returned false with empty failed criteria. The known paid lower bound
is **$2.609979026294**; unknown charges remain. This is no full-suite scorecard.

That judge gap also occurs in the [second full run's](https://github.com/lagarcess/argus/blob/dcde9affb92abd16488310ac44e91ef9d5f7c6dc/docs/reports/evidence/registry/live-measurement-second.json)
`graceful_recovery_spanish_weekly_options_aapl`, already failed on other checks,
so its totals stay unchanged. [Baseline 411's](https://github.com/lagarcess/argus/blob/dcde9affb92abd16488310ac44e91ef9d5f7c6dc/docs/reports/evidence/411/live-measurement.json)
`messy_spanish_future_performance_nvda_cruce_dorado` is a hidden false pass:
analytically 60/2 instead of native 61/1. Frozen evidence is not regraded.
Browser evidence proves authored fixture rendering only. This note made no
provider calls and authorizes no new evaluation or fingerprint change.
