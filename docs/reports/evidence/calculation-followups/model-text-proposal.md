# Exact model-facing text for founder review

This is the pre-measurement checkpoint. No live measurement has run. The new tool declarations and `requires_new_facts` schema are implemented but unmeasured. The answer instruction replacement and field descriptions below are proposed, not active. The judge additions remain proposed. No fingerprint has been refrozen.

## ResearchQueryExtraction.requires_new_facts

Compatibility default: `true`. Exact implemented description:

```text
True when answering the current question requires external facts not already available in the conversation. False when conversation history, existing artifacts, and the user's stated inputs suffice, including recalculation with changed inputs or explanation of an earlier answer. A named asset or a follow-up alone does not require new facts.
```

## AnswerCalculation field descriptions

### AnswerCalculation.prior_artifact_id

```text
For a follow-up changing a computed card, its artifact_id from calculation_cards in conversation history; null for a new calculation or a pending question. Never invent an artifact id.
```

### AnswerCalculation.updated_fields

```text
Names of inputs explicitly changed by the current user message. Omitted known inputs retain their stored values and sources. Filling a requested blank does not require listing it here.
```

### AnswerCalculationInput.currency

```text
For a money amount, the ISO 4217 currency explicitly stated by the user or its cited page; null when no currency was stated, or for a non-money input.
```

## Shared answer instructions

Replace `ANSWER_CALCULATION_INSTRUCTIONS` with this exact string in both the no-search and research answer paths:

```text
Fill calculations only when the answer computes on specific figures, such as what a plan, loan or purchase costs, what an amount earns or grows to, how many years a sum takes to double, which option costs less or what a dividend yields at today's price, each with the one kind listed below that computes it. When the reader weighs options, fill one calculation for each option under its own short name, with the same kind when one kind computes them all, and never say which option to choose. Argus computes each one: never compute a figure yourself, such as a change, a percentage, a ratio or a total; state each figure as its source gives it, or let a calculation produce it. List every input the kind needs with its source: page for a figure read from a page retrieved for this answer, with that page's URL and date; market_data for the current price of the named asset, which Argus fills from its own market data; user for a figure the user stated; assumption for any other figure you choose, which the answer must state plainly as an assumption. When the reader states a currency, add its ISO 4217 code as the currency input with source user. When a retrieved page states the currency, preserve that currency and source. When no currency is stated, omit the currency input and leave each unstated money-input currency null: Argus uses the resolved profile currency and records it as an assumption. Never choose USD or infer a currency from the response language. A currency conversion uses the input amount's currency and a separate output_currency, with the rate in the quotation direction declared by the calculation. A figure only the user knows that the user did not state is listed with source user and a null value. Only when you fill calculations, write each figure a calculation uses or produces as {{name}}, with its input or result name, or as {{calculation_name.name}} when there is more than one calculation, never as digits, including in a worked example; Argus fills each one from the computed result. Every other figure is written in digits and is never a reference. Leave calculations empty when the answer computes nothing. Calculation cards in conversation history own their inputs, sources and results; the accompanying answer_text is qualitative context, not a competing source of numbers. A reply supplying a requested input or changing an input must return the calculation that computes the new result, even for simple arithmetic. For an existing card, use its prior_artifact_id and list only explicitly changed inputs in updated_fields; keep its kind and solve_for. For a pending calculation, keep its name, kind and solve_for, fill the supplied blanks, and list any explicitly changed known inputs in updated_fields. Once the inputs suffice, state what the card computed and do not ask again for an input already supplied. When a product comparison needs personal facts that are missing, name what to compare and which facts are missing, and select nothing. Do not call any named product the best choice, closest fit or general recommendation for this reader. Reason about currency risk from the spending goal as it stands in the current turn. Savings in currency A funding a fixed expense in currency B lose purchasing power when B appreciates against A, equivalently when A depreciates against B. Matching the savings to B removes that currency mismatch; do not carry forward a replaced spending goal. When asked about putting money in a volatile asset, request historical_drawdown for that asset. If only an asset class is named, identify the asset used as a representative example. State the computed historical drawdown and actual observation window, distinguish history from a forecast, then stop. Do not replace the result with a risk essay, a product choice or further questions. Kinds, their inputs and their results:
```

## Registered calculation catalogue additions

These exact generated catalogue lines are already implemented. No separate handwritten catalogue is proposed:

```text
- scaled_amount: Multiply or divide an amount by a stated percentage or multiple, without imposing a time period. Percent means rate / 100; multiple means the rate itself. For currency conversion, currency is the amount's currency and output_currency is the result's currency: multiply a quote in output currency per input currency, or divide a quote in input currency per output currency. Inputs: currency, amount, rate, rate_unit (percent or multiple), operation (multiply or divide), output_currency. Results: scaled_amount.
- historical_drawdown: Measure an asset's worst historical peak-to-trough percentage decline from Argus market-data daily closes. Supply the symbol and optional start_date/end_date; omitted dates use five years ending yesterday. The result reports the actual observation window, not an all-time or intraday loss, and does not predict future losses. Inputs: symbol, start_date (ISO date), end_date (ISO date). Results: max_drawdown_pct, observations.
```

## Prose judge additions

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

## Measurement boundary

After founder go: apply the proposed answer/field/judge text, run the existing sanctioned measurement with all 93 cases (including 22 new English/Spanish cases), retain costs and exact-head provenance, evaluate failures honestly, and refreeze only if the evidence passes. The authored-history cases measure a live follow-up against a real loader projection; they do not by themselves prove a preceding live turn persisted correctly. Bilingual browser acceptance and the original two-turn reproductions remain part of final lane acceptance. Stop on a second Codex finding on the same mechanism.
