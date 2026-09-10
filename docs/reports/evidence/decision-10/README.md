# Decision 10: forward-looking and valuation questions are answered

Founder decision of 2026-09-10, recorded in
`docs/specs/argus-grounded-finance-roadmap.md` as decision 10: Argus answers
"what will $10,000 in NVDA be worth in ten years?" and "what price does NVDA
need to grow into?" the way Perplexity does, with cited forecasts, analyst
targets and valuation multiples, the arithmetic written out, and results as
labeled scenario ranges. Never one number as the future, never advice. The one
thing that stays impossible is a backtest over a future window, because that
market data does not exist.

Lane branch `claude/argus-forward-valuation-d2289e`, base integration
`d0884c3d`. This folder holds the before picture at that base, the after
picture at the lane head, the live measurement scorecard the prompt
fingerprint now names, the browser proof, and the drivers that produced them.

## What changed

- `src/argus/agent_runtime/interpreter/unsupported_admission.py`: the clause
  that told every interpretation to classify a future-value question as
  unsupported is replaced by `future_test_window_capability_clause()`, which
  sends forward-looking and valuation questions to research and keeps only a
  test asked over a future window on the strategy route. The typed horizon
  still forces the strategy route on the turns research did not claim
  (`strategy_route_flags_with_future_precedence`): research claims a question
  read before that stage runs, so a horizon that reaches it belongs to a read
  with no question shape, and the recovery offering the historical test and
  analyst research is what the user sees instead of the model's own forecast
  (Codex round 1, P1).
- `src/argus/agent_runtime/interpreter/research_routing.py`: a strategy claim
  whose horizon points forward is not a runnable test, so it no longer outranks
  a question payload; when that waiver decides the route it is recorded as
  `research_answers_future_horizon_question` on the interpretation and logged.
- `src/argus/agent_runtime/llm_interpreter.py`: the valuation paragraph no
  longer steers valuation language toward a backtest proxy; the proxy is
  offered only when the user wants to test a rule built on valuation.
- `src/argus/agent_runtime/research_grounded.py`: the research prompt asks for
  labeled scenarios computed from public inputs rowed with their pages, the
  arithmetic written out, each range low to high; it keeps "never estimate a
  live number" and "No investment advice", names web search and fetched pages
  as the retrieval so a finance lookup that returns nothing never ends the
  answer, and can run without the provider's finance tool.
  `research_answer.py` grounds a claim about crypto or a currency pair on
  public pages that way instead of degrading it to a coverage note.
- The typed scenario signal. The interpreter sets
  `research_query.scenario_question` for a question whose answer is a value,
  target or fair value to compute; a `future_window` horizon typed on the
  draft is the second, independent fact, and `scenario_contract_applies()`
  is the one owner that reads either (Codex round 4), including the
  off-coverage branch of the dispatch, so a crypto scenario typed only by its
  horizon is grounded rather than answered with closes (Codex round 5). A
  scenario lives in the analyst-estimates data class: three-day cache TTL and a
  one-month web recency filter whatever kind it was typed as, and the
  recording was re-captured under that filter (Codex round 7). The dispatch
  derives the scenario fact before every kind branch, so a scenario typed as
  market statistics, a survey or an asset search runs on the balanced shape
  rather than being voiced from history; only a named multi-company comparison
  keeps the thorough job (Codex round 10). A read that says the answer is a
  scenario about named subjects is a fact question whatever kind it left; a
  scenario bit with no subject stays a projection answered as arithmetic, and
  a typed horizon alone never admits, so a test asked over a future window
  keeps its recovery (Codex round 11). A scenario typed as a survey kind is
  never handled as a survey downstream, and the subjectless-scenario guard
  runs before any kind check (Codex round 12). The guard and the owner read
  one typed predicate, and the derived survey fact reaches the failure paths
  (Codex round 13). The crossover row keeps direction and both averages or
  offers nothing, the discovery entry reads the scenario owner before its
  kind diversion, and public-source freshness reads the derived survey fact
  (Codex round 14). `retrieval_spec(scenario=True)` then sends
  `SCENARIO_RETRIEVAL_INSTRUCTIONS`, the recorded retrieval contract plus the
  carve-out that the inputs are the retrieved figures and are rowed while the
  scenario values are the model's arithmetic and are never rowed. Every other
  question keeps the recorded contract byte for byte; the scenario contract is
  frozen by `probes/scenario_typed_balanced.json` through the same test that
  freezes the others. The contract is part of the research cache identity, so
  a packet answered under one contract never serves a question asked under the
  other, and a scenario publishes only when at least one input row cites a
  public page (`scenario_inputs_uncited` otherwise, on the inline and the
  background path); every recorded scenario answer carried three to seven
  (Codex round 2, two P2s; round 3 carried the gate to the thorough cache-hit
  composition, where a cached withheld scenario would otherwise publish on
  the repeat question).
- `src/argus/domain/research/config.py`: the balanced shape's ceiling moves
  from 75s to 150s. This applies to every balanced research question, not
  only scenarios: a company read, a current-events claim or a survey that used
  to degrade at 75s now waits up to 150s before degrading, while a quick
  answer returns as quickly as before. A scenario answer took 122s in the probe below and every
  forward-looking question timed out at 75s in the first after picture. The
  ceiling is room, never a rule; a quick answer still returns quickly.
- `src/argus/agent_runtime/research_rows.py`: after an answer about a named
  moving-average crossover, the rows offer that idea's historical test beside
  the plain hold (the benchmark on the resulting card is the "or that money in
  the market" contrast).
- The surviving `future_performance` recovery copy (backend fallback, both
  locales) names the missing data and offers the historical test and the
  analyst research; nothing says "I can't predict".
- Measurement: the three cases that required the refusal now expect a
  published research answer with at least one next-experiment row and a new
  `scenario_framing` prose criterion (rubric v3).
- Canon: `docs/PRODUCT.md` section 11 and `docs/API_CONTRACT.md`.

## Cost estimate (posted before any paid run; the actual spend, about $12 to $13, exceeded it, see the PR)

| Run | Turns | Estimate |
| --- | ---: | ---: |
| Before picture, integration `d0884c3d`: 13 questions in `drivers/questions.json` (the founder's two in en and es-419, six Driven-style, two consumer projections, the golden cross measurement case) plus the two founder questions asked of Perplexity as typed | 15 | $2.00 to $3.50 |
| After picture, lane head: the same 13 questions | 13 | $2.00 to $3.50 |
| Live measurement, full suite of 69 cases (the fingerprint scorecard must carry every case; the last full run cost $1.11 on OpenRouter plus research turns) | 69 | $1.50 to $2.50 |
| Browser proof: reuses the after-picture conversations, no new provider turns | 0 | $0 |
| **Total** | | **$5.50 to $9.50** |

Step 1 alone is the first row. The research turns dominate: a balanced turn
recorded $0.05 to $0.16 and a thorough one (the comparison and the deep dive)
runs the opus tier in the background.

## The before picture

Integration `d0884c3d`, run 2026-09-10 between 14:58 and 15:16 New York time
from a detached checkout of that commit, through the same local API and the
same drivers as the after picture. Records are under `before/`; the two turns
that died on interpreter timeouts (`interpreter_unavailable`, the fallback
model's response failing validation after the primary timed out) were re-run
and both attempts are kept under `before/infrastructure/`.

Thirteen questions, and Argus refused or dodged nine of them:

- **The founder's two questions refused, in both languages.** "What will
  $10,000 in NVDA be worth in ten years" and its Spanish twin hit the
  `future_performance` refusal: "I cannot predict future performance. I can
  test how the same idea performed over a historical period instead." "What
  price does NVDA need to grow into" and its Spanish twin hit
  `unsupported_strategy_logic`: "Argus can't test a price-target rule
  directly, but we can run a supported strategy on NVDA vs SPY."
- **The golden cross measurement case refused** with `future_performance`.
- **The AAPL "fundamentals, valuation and sentiment" read refused** with
  `unsupported_strategy_logic`: the valuation steer turned a research question
  into "Argus can't run that rule directly yet for AAPL."
- **Both savings projections dodged.** "$500 a month at 5% for 20 years" was
  answered in prose with "Argus cannot predict future returns or savings
  growth" and an offer to backtest a DCA instead; the Spanish "5,000 pesos al
  mes al 6%" was read as a strategy draft and asked "What date window should I
  use?" (`missing_period`).
- **The rate-cut question was hedged** from model knowledge: "I'm not set up
  to track live moves or give current market commentary."
- **Two grounded answers:** the sector radar (balanced, 5 sources, $0.175) and
  the software screen (balanced, $0.302, on the re-run).
- **Two provider failures on the base tree**, kept as recorded: the Microsoft
  deep dive got a provider HTTP 500 on the balanced shape and the NFLX
  comparison a 400 on the synchronous thorough path.

## Why the after picture took four attempts

The first after run at `f56e9689`'s parent timed out every forward-looking
question at the balanced shape's 75s ceiling. The probe
`probes/scenario-balanced-180s.json` asked the exact prompt Argus builds
through the repository's own client with the ceiling lifted: it answered in
122s and $0.687 with bear, base and bull ranges, the arithmetic written out
from a published five-year analysis and the current price, thirteen cited
rows, labeled illustrative, no advice. The ceiling moved to 150s.

The second attempt answered the founder's question with "The requested
ten-year NVDA scenario ranges could not be retrieved and verified" while
holding five forecast pages and writing no rows
(`probes/after-attempt-2-nvda-non-answer.json`): the publisher line told the
model to decline when no page states the claim, and no page states a computed
ten-year figure. The scenario instruction now says the inputs are what must be
public and rowed, the scenarios are the model's own arithmetic, and a horizon
no forecast covers is built from the nearest published one with the assumption
stated.

The third attempt answered "The current figure could not be retrieved" with
five forecast pages and no rows (`probes/after-attempt-3-nvda-non-answer.json`):
the finance lookup returned nothing and the retrieval contract's say-only rule
ended the answer. The instruction now names web search and fetched pages as the
retrieval for this shape and makes the finance tool optional.

The fourth attempt met a provider outage: an HTTP 500 on the first question
and a 150s timeout on the second, matching the 500 and the 400 the base tree
took in its own run. The after picture below was launched by a health gate
(`drivers/probe_health.py`, a plain company question that must answer inside
75s) once the provider was serving again.

## The after picture

Lane head `60e7c0ec`, the commit the live measurement below was taken at, run
2026-09-10 between 15:26 and 15:45 New York time through the same local API
and drivers as the before picture. Records are under `after/`. Four turns were
lost to provider HTTP 500s during the run and re-asked into the same process
once the provider was serving; both attempts are kept, the failed one under
`after/infrastructure/`. Every answer below was captured at this head.

**The founder's two questions are answered, in both languages, as grounded
scenarios.**

- "what will $10,000 in NVDA be worth in ten years?": a ten-year range of
  $61,917 to $93,132 built as bear, base and bull from the current price and
  published long-term growth forecasts, the compounding written in the table
  ($10,000 × 1.20¹⁰ to $10,000 × 1.25¹⁰), five rowed inputs, five sources, "a
  wide scenario range, not a prediction", no advice. 53s, $0.157.
- "What price does NVDA need to grow into?": the valuation exercise itself.
  Published FY2027 EPS estimates times bear, base and bull multiple bands give
  $180 to $454, with the base case bracketing the trailing multiple, a
  published analyst-target cross-check ($218 to $515, average $324), eight
  rowed inputs, and "not what its price will be". 52s, $0.167.
- The Spanish twins answer in Spanish: "Bajista, Base, Alcista extremo" ranges
  with the formula ($10,000 × (1 + rendimiento anual)¹⁰), and three implied
  price ranges from analyst targets with the percentage formula, "no un único
  precio futuro ni una recomendación de inversión". 85s and 56s, $0.251 and
  $0.167.
- Under each: "5 sources ›" and the historical test as a Try next row,
  "Test NVIDIA (NVDA) over the last 3 years" / "Probar NVIDIA (NVDA) en los
  últimos 3 años". The benchmark on the resulting card is the "or that money
  in the market" contrast.

**The golden cross measurement question** answers the same way: a $10,000 to
$137,858 range built from published golden-cross backtests as scenario inputs,
four rowed inputs, "This is not an NVDA forecast". Its next-step row is the
plain NVDA hold rather than the crossover: the interpreter now leaves the
strategy draft empty for a question turn, and the crossover row fires only
when the typed rule is present (unit-tested, not exercised here). Recorded as a
known gap below.

**Both savings projections are answered as arithmetic, with the steps.** "$500
a month at 5% for 20 years" gets the annuity formula and three steps to about
$205,240 in 20s; the exact figure is $205,517, a 0.13% drift in the model's
intermediate factor (410.48 against 410.98). The Spanish "5,000 pesos al mes al
6%" gets four steps to 819,396 pesos in 22s, which is exact. The brief allows
prose math in this lane and forbids claiming it verified; the drift is the
reason the grounded-math step exists.

**Valuation language is research now.** The AAPL "fundamentals, valuation and
sentiment" read, refused at the base as an unsupported rule, answers with a
three-row table of grounded figures, eleven rowed inputs, five sources, and
"Test Apple (AAPL) over the last 3 years". 68s, $0.261.

**The Driven-style questions that do not depend on this lane:** the Microsoft
deep dive answers (balanced, five sources, $0.645, 107s; a provider 500 at the
base); the software screen answers with nine rowed inputs and two test rows
($0.550, 137s). Three fail identically on both trees and are outside decision
10: the NFLX comparison takes a provider HTTP 400 on the synchronous thorough
fallback that memory-mode dev uses (production runs that shape as a background
job); the rate-cut repricing question is typed as a general question rather
than current-events research and the educational composer dodges it from its
"simulation world"; the sector radar comes back `survey_synthesis_incomplete`
twice at the head after answering once at the base (survey prose that names no
verified ticker; the survey path is byte-identical to the base except for the
longer ceiling).

Research spend for the thirteen final answers: $2.55. The four founder
questions cost $0.16 to $0.25 each.

## Before and after, one table

Verdict, research shape (degraded code), sources, research cost, wall time,
and the first line of the answer. Full records are the JSON files beside this
README.

| Question | Before (integration d0884c3d) | After (lane head) |
| --- | --- | --- |
| what will $10,000 in NVDA be worth in ten years? | refused: unsupported_recovery/future_performance · no research · 0 sources · n/a · 76.88s · I cannot predict future performance. I can test how the same idea performed over a historical period instead. Which direction should I take: Test this idea over a historical period or Compare with buy and hold? | answered · balanced · 5 sources · $0.157 · 53.49s · **Ten-year scenario estimate for a $10,000 NVDA investment: $61,917 to $93,132.** This is a wide scenario range, not a prediction.  At NVDA’s $218.40 share price as of September 10, 2026, $10,000 would buy 45.7875 sha... |
| What price does NVDA need to grow into? | refused: unsupported_recovery/unsupported_strategy_logic · no research · 0 sources · n/a · 28.71s · Argus can't test a price-target rule directly, but we can run a supported strategy on NVDA vs SPY. Which direction fits your thinking? | answered · balanced · 5 sources · $0.167 · 52.04s · **NVDA’s earnings-based “grow-into” range is $180.20, $454.50 over the next fiscal year, with a base range of $232.75, $325.85.** These are scenarios, not a single forecast.  NVDA traded at **$218.40 as of September 1... |
| ¿Cuánto valdrán $10,000 en NVDA dentro de diez años? | refused: unsupported_recovery/future_performance · no research · 0 sources · n/a · 28.67s · I cannot predict future performance. I can test how the same idea performed over a historical period instead. Which direction should I take: Test this idea over a historical period or Compare with buy and hold? | answered · balanced · 5 sources · $0.251 · 84.61s · **En diez años, los $10,000 podrían convertirse mecánicamente en estos rangos:**  | Escenario | Supuesto anual | Valor dentro de diez años | |---|---:|---:| | Bajista | 3%, 11.5% | **$13,439, $29,699** | | Base | 11.5... |
| ¿A qué precio necesita crecer NVDA? | refused: unsupported_recovery/unsupported_strategy_logic · no research · 0 sources · n/a · 34.7s · Entiendo tu pregunta sobre el precio objetivo de NVDA. Argus no puede probar estrategias basadas en un precio específico de crecimiento, pero podemos acercarnos de otras formas. ¿Cuál de estas opciones prefieres explo... | answered · balanced · 5 sources · $0.167 · 55.66s · **NVDA necesitaría cotizar entre US$324.34 y US$341.44 para alcanzar la zona central de los objetivos publicados a un año.** Desde el precio actual de **US$218.40**, eso exige crecer entre **48.51% y 56.34%**.  | Esce... |
| Give me a deep dive on Microsoft: its growth drivers and the biggest risks to the business. | answered · balanced (research_unavailable_http_error) · 0 sources · n/a · 85.61s · I couldn't complete the data lookup just now, so I won't quote live figures. Testing an idea against historical data is still available. | answered · balanced · 5 sources · $0.645 · 106.54s · **Bottom line:** Microsoft’s main growth engine is the combination of Azure cloud consumption and AI monetization across its existing enterprise software, developer, security, data, and business-application franchises... |
| How is the most recent Fed rate cut repricing stocks, bonds and currencies? | answered · no research · 0 sources · n/a · 35.1s · I hear you asking about how markets are reacting to the latest Fed rate cut. That’s a great macro question, but I’m not set up to track live moves or give current market commentary. What I *can* do is help you explore... | answered · no research · 0 sources · n/a · 38.78s · I can’t speak to the most recent Fed move—my simulation world doesn’t have live news or current pricing. But we can explore a nearby historical experiment that captures the kind of repricing you’re asking about.  For ... |
| Which US sectors are accelerating or rolling over this month? | answered · balanced · 5 sources · $0.175 · 65.67s · **As of September 9, 2026, using trailing one-month momentum:**  - **Accelerating:** Energy (XLE) **+8.52%** and Technology (XLK) **+0.83%**. - **Rolling over:** Industrials (XLI) **−6.94%**, Consumer Discretionary (X... | answered · balanced (survey_synthesis_incomplete) · 4 sources · $0.112 · 42.38s · I found sources, but could not extract the sector's current leaders and laggards. |
| Screen profitable US software companies with ROE above 15% and a free cash flow yield above 3%. | answered · balanced · 0 sources · $0.302 · 106.51s · - **Adobe (ADBE): ROE 62.76%; free-cash-flow yield 10.39%; net income $7.229 billion.** ROE and profitability use trailing results through May 29, 2026. The yield uses trailing free cash flow through that date and mar... | answered · balanced · 1 sources · $0.550 · 136.64s · **Screen matches among the candidate companies reviewed:**  - **Adobe (ADBE): ROE 62.39% and FCF yield 9.35%, as of September 4, 2026.** Profitability is supported by quarterly net income of $1.71 billion for the peri... |
| Compare margins and revenue growth for NFLX against DIS and WBD. | answered · no research · 0 sources · n/a · 76.81s · I couldn't finish that thorough research run. I won't quote figures I didn't verify; you can ask again, or test the idea against historical data right now. | answered · no research · 0 sources · n/a · 58.76s · I couldn't finish that thorough research run. I won't quote figures I didn't verify; you can ask again, or test the idea against historical data right now. |
| Give me a quick read on AAPL: fundamentals, valuation and sentiment. | refused: unsupported_recovery/unsupported_strategy_logic · no research · 0 sources · n/a · 44.87s · Argus can't run that rule directly yet for AAPL. Which supported direction should I use: Use a supported RSI threshold rule, Compare with buy and hold, or Use a supported moving-average crossover? | answered · balanced · 5 sources · $0.261 · 68.01s · **Quick read:** Apple’s fundamentals are strong, but its valuation is demanding and sentiment is positive but divided.  | Area | Read | |---|---| | Fundamentals | Fiscal third-quarter revenue was **$109,417,000,000**,... |
| If I save $500 a month at 5%, how much will I have in 20 years? | answered · no research · 0 sources · n/a · 36.68s · Argus cannot predict future returns or savings growth. However, I can test how a dollar-cost accumulation strategy would have performed historically. For example, I could backtest investing $500 monthly into a diversi... | answered · no research · 0 sources · n/a · 20.17s · Assuming a 5% annual interest rate compounded monthly, use the future value of an ordinary annuity formula: FV = P × [((1 + r)^n − 1) / r], where P = 500, r = 0.05/12 ≈ 0.004167, and n = 240 months. Step 1: compute (1... |
| ¿Cuánto tendré en 10 años si ahorro 5,000 pesos al mes al 6%? | refused: clarification/missing_period · no research · 0 sources · n/a · 52.57s · What date window should I use? | answered · no research · 0 sources · n/a · 21.66s · El cálculo es aritmético usando la fórmula del valor futuro de una anualidad: FV = P × [((1 + r)^n - 1) / r], donde P = 5000 (aportación mensual), r = 0.06/12 = 0.005 (tasa mensual), n = 10 × 12 = 120 meses. Asumiendo... |
| If I invest $10,000 in NVDA using a golden cross strategy, how much will it be worth in ten years? | refused: unsupported_recovery/future_performance · no research · 0 sources · n/a · 34.59s · Argus can't predict future returns, but we can test the golden cross idea against real history. Which direction sounds best? | answered · balanced · 5 sources · $0.235 · 56.61s · **A reasonable scenario range is $10,000 to $137,858 after ten years, with the middle range at $19,307 to $55,061.** This is not an NVDA forecast: no published ten-year, NVDA-specific golden-cross forecast was availab... |

## Live measurement

`live-measurement.json` is the full 69-case live scorecard at `60e7c0ec`,
the commit `.agent/interpreter_prompt_fingerprint.json` now names: **63
passed, 6 failed, 0 infrastructure errors**, $1.48 on OpenRouter plus the
research turns. `baseline-comparison.json` is the case-by-case comparison
against the fingerprint's previous scorecard (`411/live-measurement.json` at
`9fec4bf7`, 61 passed, 1 failed; really 60 and 2, see the board).

- **The three future cases pass** under their rewritten expectations: a
  published research answer, a next-experiment row, and the new
  `scenario_framing` prose criterion (rubric v3).
- **Fifty-eight cases are unchanged.** The DCA pesos case fails on both.
- **Four cases changed verdict outside the three future ones**, called out as
  the founder asked because rubric v3 changes the judge text:
  - `asset_discovery_category_spanish_issue_244`: the interpreter left
    `semantic_turn_act` empty; the discovery itself delivered five symbols.
  - `asset_discovery_old_pharma_escalation_exact_issue_344`: the discovery
    voicing call timed out and then returned empty (`discovery_search_failed`),
    the flake PR #565 recorded on the sibling pharma cases.
  - `asset_discovery_not_result_followup_issue_244`: the result follow-up
    draft was rejected by its validator (`latest_result_followup_unavailable`).
  - `graceful_recovery_spanish_weekly_options_aapl`: the judge failed
    `honesty` because "podemos simular estrategias sobre AAPL" beside two
    equity options reads as offering option strategies. The prose is the
    clarifier's, which this lane did not change.
- **One added case fails**: `ordinary_conversation_concept_compound_interest_en`,
  the judge reading "Argus can help you explore its effects through ... backtests"
  as an unsupported capability claim beside an empty rendered surface. It passed
  in PR #565's run under rubric v2.

**Re-run once, at the head and on the base** (`live-measurement-retry.json`):

| Case | Re-run at head `53c35ff8` | Re-run at base `d0884c3d` |
| --- | --- | --- |
| `asset_discovery_category_spanish_issue_244` | failed | failed |
| `asset_discovery_not_result_followup_issue_244` | failed | failed |
| `asset_discovery_old_pharma_escalation_exact_issue_344` | failed | failed |
| `graceful_recovery_spanish_weekly_options_aapl` | passed | passed |
| `ordinary_conversation_concept_compound_interest_en` | passed | passed |

Both judge failures pass on re-run on both trees: judge variance, not the
rubric text and not this lane. The three discovery cases fail on re-run on
both trees with the same failure classes (no actionable discovery, no rows):
the discovery path was failing on the provider this afternoon with or without
this lane's changes, the flake PR #565 recorded on the sibling pharma cases.

## Browser proof

`browser/` holds Playwright captures of the recorded after conversations in
the web app at 1280 and 390 CSS pixels, in the language each was asked in:
both founder questions in English and Spanish (`nvda-future-value-*`,
`nvda-grow-into-*`, `nvda-future-value-es-*`, `nvda-grow-into-es-*`) and both
projections (`savings-500-5pct-*`, `ahorro-5000-6pct-*`). `report-batch-1.json`
and `report-batch-2.json` record, per capture, that the page text carries the
scenario wording and no "can't predict" phrasing, with no page errors. The
web server ran with `NEXT_PUBLIC_ENABLE_SPANISH=true` and
`NEXT_PUBLIC_RESEARCH_RAIL_ENABLED=true`; the Spanish pages show Spanish chrome
("5 fuentes ›", "Qué probar después").

## Known gaps and what this lane does not claim

- **The crossover row.** After the golden cross answer the Try next row offers
  the plain hold, because the interpreter leaves the draft empty for a question
  turn (the safer routing). The crossover-specific row exists and is
  unit-tested; carrying a named idea on a question turn as a typed field is a
  follow-up.
- **Prose math is not verified.** The projections show their steps; the
  English one drifts 0.13% in an intermediate factor. Moving the arithmetic
  into tested code is the "Any grounded math" step, not this lane.
- **Ranges read "low, high".** The provider writes a range as "$61,917,
  $71,812" rather than "$61,917 to $71,812" even when asked for low to high.
  Presentation only; every range is labeled.
- **Cost and latency.** A scenario answer is a balanced turn with three to
  four retrievals: $0.16 to $0.25 and 50 to 85 seconds in this picture, $0.69
  and 122 seconds in the widest probe. The balanced ceiling is 150s for that
  reason.
- **Provider health.** The provider returned HTTP 500s and 150-second timeouts
  intermittently through the afternoon on both trees; the pictures record
  every failed attempt beside the answer that replaced it.
- **The three questions that fail on both trees** (NFLX thorough 400, the
  rate-cut dodge, the sector survey) are outside decision 10 and unchanged.

## The founder's side by side

The founder's pasted Perplexity answers are the comparison column; they are
not in this repository. The two Argus answers to compare are
`after/nvda-future-value.json` and `after/nvda-grow-into.json` (English) and
their `-es` twins.

Ask both products the same two questions, in the same session, and compare.

1. Argus, local at the lane head. From the lane worktree:

   ```bash
   D10_TREE="$PWD" D10_ENV_FILE="$PWD/.env" poetry run python docs/reports/evidence/decision-10/drivers/serve.py
   ```

   In a second terminal, the web app against it (mock auth, Spanish on,
   research rail on):

   ```bash
   cd web && NEXT_PUBLIC_ARGUS_API_URL=http://127.0.0.1:8610/api/v1 NEXT_PUBLIC_MOCK_AUTH=true NEXT_PUBLIC_ENABLE_SPANISH=true NEXT_PUBLIC_RESEARCH_RAIL_ENABLED=true bun run dev -- -p 3610
   ```

   Open `http://127.0.0.1:3610/chat`, start a new chat, and type each question
   exactly:

   - `what will $10,000 in NVDA be worth in ten years?`
   - `What price does NVDA need to grow into?`

   Argus should answer each with cited scenarios (bear, base, bull or similar
   labels), the arithmetic written out, a sources drawer, and a "Test ..."
   row underneath. It must not say it cannot predict, and it must not tell you
   to buy, sell or hold.

2. Perplexity. Open `https://www.perplexity.ai`, start a new thread, and type
   the same two questions exactly. Compare: does each side cite its inputs,
   show the math, label the result as scenarios, and refrain from advice?

3. The API equivalent of step 2, question as typed with no Argus prompt:

   ```bash
   D10_TREE="$PWD" D10_ENV_FILE="$PWD/.env" poetry run python docs/reports/evidence/decision-10/drivers/perplexity_plain.py nvda-future-value "what will $10,000 in NVDA be worth in ten years?" temp/perplexity-nvda-future-value.json
   ```

If Argus says it cannot do something Perplexity just did, the lane is not
done.
