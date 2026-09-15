# Exact model-facing text for founder review

The founder approved this text and gave measurement go. The answer instruction replacement, field descriptions, and judge additions below are now active exactly as shown, including the general A/B currency-risk rule. The judge is version 4. No fingerprint has been refrozen; measurement results must establish acceptance. The approved budget is enforced by the measurement-only transport guard.

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

## Registered calculation catalogue

These exact generated lines derive result reference names from the same projections that render the cards. Conditional names are marked; the catalogue never computes an example or calls a market provider. Argument names remain the tool's input schema.

```text
- time_value: Solve a saving or borrowing plan for the one blank among starting amount, payment per period, ending amount, annual rate and number of periods. Covers savings goals, affordability, loans, amortization and certificates. Money is in the stated currency; zero is a known value. Inputs: currency, direction (save or borrow), present_value, payment, future_value, annual_rate_pct, periods, periods_per_year, payment_timing (end or start), start_date (ISO date). Exactly one blank among present_value, payment, future_value, annual_rate_pct, periods. Results: present_value (when present), payment (when present), future_value (when present), annual_rate_pct (when present), periods (when present), total_payments, total_interest (when present), total_growth (when present).
- scaled_amount: Multiply or divide an amount by a stated percentage or multiple, without imposing a time period. Percent means rate / 100; multiple means the rate itself. For currency conversion, currency is the amount's currency and output_currency is the result's currency: multiply a quote in output currency per input currency, or divide a quote in input currency per output currency. Inputs: currency, amount, rate, rate_unit (percent or multiple), operation (multiply or divide), output_currency. Results: scaled_amount.
- growth_projection: Project a balance that compounds at an annual rate with optional periodic contributions, solving for the one blank among starting value, ending value, annual rate and number of periods, and show the ending value and rate after inflation. Inputs: currency, start_value, contribution, end_value, annual_rate_pct, periods, periods_per_year, inflation_rate_pct. Exactly one blank among start_value, end_value, annual_rate_pct, periods. Results: start_value (when present), end_value (when present), annual_rate_pct (when present), periods (when present), total_contributed, growth, real_end_value, real_annual_rate_pct.
- bond_value: Price a bond or certificate from its face value, coupon rate, term and yield to maturity, or find the yield to maturity a price implies. Exactly one of price and yield is blank. Inputs: currency, symbol, face_value, coupon_rate_pct, years, coupons_per_year, price, yield_to_maturity_pct. Exactly one blank among price, yield_to_maturity_pct. Results: price (when present), yield_to_maturity_pct (when present), current_yield_pct, annual_coupon, total_coupons, total_return.
- discounted_cash_flow: Value a stream of cash flows that grow for a number of years and then at a terminal rate, discounted at a required rate; or, given a value or price, find the growth it implies. Exactly one of value and growth is blank. Inputs: currency, symbol, cash_flow, growth_rate_pct, discount_rate_pct, years, terminal_growth_rate_pct, value. Exactly one blank among value, growth_rate_pct. Results: value (when present), growth_rate_pct (when present), cash_flow_at_horizon.
- price_multiple: Relate a price to a per-share figure through a multiple such as price to earnings, price to cash flow or price to book: give any two of price, per-share figure and multiple and the third is solved. Inputs: currency, symbol, price, per_share, multiple. Exactly one blank among price, per_share, multiple. Results: price (when present), per_share (when present), multiple (when present), earnings_yield_pct.
- income_yield: Relate yearly income to a price as a yield, for dividends, rent, interest or coupons: give any two of yearly income, price and yield. Inputs: currency, symbol, annual_income, price, yield_pct. Exactly one blank among annual_income, price, yield_pct. Results: annual_income (when present), price (when present), yield_pct (when present), monthly_income.
- effective_rate: Turn a nominal yearly rate into the effective yearly rate under its compounding, and when a loan amount, fees and a number of payments are given, the effective APR the fees raise it to, with the payment and total cost. Inputs: currency, nominal_rate_pct, compounding_per_year, amount, fees, periods. Results: effective_rate_pct, payment (when present), total_paid (when present), total_cost (when present).
- debt_to_income: Monthly debt payments as a share of monthly income: give any two of monthly debt payments, monthly income and the ratio. Inputs: currency, monthly_debt_payments, monthly_income, ratio_pct. Exactly one blank among monthly_debt_payments, monthly_income, ratio_pct. Results: monthly_debt_payments (when present), monthly_income (when present), ratio_pct (when present), income_after_debt.
- expense_ratio: A yearly fee as a share of assets, or the fee a ratio charges, and what that fee costs over a number of years at a stated growth rate. Exactly one of the yearly fee and the ratio is blank. Inputs: currency, symbol, assets, annual_fee, ratio_pct, years, growth_rate_pct. Exactly one blank among annual_fee, ratio_pct. Results: annual_fee (when present), ratio_pct (when present), cost_over_years, ending_with_fee, ending_without_fee.
- ranked_comparison: Rank a set of products or instruments by one stated numeric key, preferring higher or lower values, and show each item's gap to the best. Items carry the figure a page or the user supplied; nothing is recommended. The ranked figures are rank_0, rank_1 and so on, from the best item. Inputs: currency, key_label, key_kind (percent or money or multiple or count), prefer (higher or lower), items (list of {label, symbol, value}). Results: rank_0 (when present), gap_0 (when present), rank_1 (when present), gap_1 (when present), rank_2 (when present), gap_2 (when present), rank_3 (when present), gap_3 (when present), rank_4 (when present), gap_4 (when present), rank_5 (when present), gap_5 (when present), rank_6 (when present), gap_6 (when present), rank_7 (when present), gap_7 (when present), rank_8 (when present), gap_8 (when present), rank_9 (when present), gap_9 (when present), rank_10 (when present), gap_10 (when present), rank_11 (when present), gap_11 (when present).
- valuation_scenarios: Build low, base and high valuation scenarios for an asset from its price, a per-share figure such as earnings or cash flow, a base growth rate with optional low and high bounds, optional multiples and a horizon in years, showing the price each scenario implies, the annual return that would mean from today's price, and what a stated amount invested today would be worth. A missing bound uses the base and a missing multiple holds today's. Inputs: currency, symbol, price, per_share, growth_low_pct, growth_base_pct, growth_high_pct, multiple_low, multiple_base, multiple_high, horizon_years, amount. Results: base_annual_return_pct (when present), current_multiple, value_at_horizon_low (when present), price_at_horizon_low, annual_return_pct_low, value_at_horizon_base (when present), price_at_horizon_base, annual_return_pct_base, value_at_horizon_high (when present), price_at_horizon_high, annual_return_pct_high.
- historical_drawdown: Measure an asset's worst historical peak-to-trough percentage decline from Argus market-data daily closes. Supply the symbol and optional start_date/end_date; omitted dates use five years ending yesterday. The result reports the actual observation window, not an all-time or intraday loss, and does not predict future losses. Inputs: symbol, start_date (ISO date), end_date (ISO date). Results: max_drawdown_pct, observed_start_date, observed_end_date, observations, peak_date (when present), trough_date (when present).
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
  Savings in currency A funding a fixed expense in currency B lose purchasing
  power when B appreciates against A, equivalently when A depreciates against B.
  Matching the savings to B removes that currency mismatch. Do not reverse the
  adverse move or carry forward a replaced spending goal.
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
