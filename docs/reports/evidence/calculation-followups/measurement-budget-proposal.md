# Proposed 93-case measurement budget

Status: founder-approved budget. The measurement-only guard now enforces the
limits below at the HTTP-send boundary. `ARGUS_EVAL_BUDGET_REPORT` is required;
a missing or blank value refuses the live run before provider work.
It leaves production retries unchanged. Live execution still requires its
explicit go and a clean reconciled head; enabling the guard alone starts no call.

## Spending proposal

Use a **$15 monitored stop budget**, including at most $8 for Agent research.
OpenRouter and Search share the remaining total; the earlier $4/$3 allocation
is no longer a separate admission cap.
Stop before dispatch when settled spend plus the reservation would exceed the
Agent cap or total. Do not automatically rerun failed cases.

This is an admission limit, **not a guaranteed maximum invoice**. The Agent API
has no verified per-request dollar ceiling; an outstanding call can cost more
than its reservation. The [Agent API request contract](https://docs.perplexity.ai/api-reference/agent-post)
documents execution controls, not a guaranteed USD maximum. A timeout also does
not prove that provider billing stopped. If an absolute $15 invoice ceiling is
required, keep measurement paused until a provider-enforced limit is verified.

Expected spend is approximately $5–9, not a bound. The existing acceptance
[content-free cost events](../2026-09-14-acceptance/cost-events.jsonl) contain 23
priced Agent requests with a $0.1486 median, $0.27826 p90, and $0.36037 maximum.
These observations do not guarantee the next request's cost.

## Bounded research admission

- At most the 16 Agent-eligible cases below may dispatch Agent work.
- **One application request and one HTTP send per eligible case: at most 16
  Agent sends for the entire measurement.** Block semantic and transport retries
  before dispatch. Record a retry-budget case failure and continue; never count that case
  as a model-quality pass or silently substitute a cheaper execution path.
- Run cases serially. A finished or cancelled call may still have an unknown bill;
  its reservation remains counted while later cases run.
- Reserve at least $1.50 before each Agent send. Read the actual `models` fallback
  list and reserve the largest estimate across every candidate's highest priced
  tier, using the request size, step count and output allowance. Reject an
  unpriced candidate before dispatch. This estimate covers initial request and
  output tokens, not an upper bound on retrieved context or tool work.
  Settle using the response-owned invoice.
  Stop before the next admission if settled plus reserved spend plus that
  admission would exceed $15 total or $8 Agent, or the next Agent send would
  exceed 16. Reservations are estimates and can be exceeded by the active call.
- Retain the reservation on cancellation, transport failure, or missing/unpriced
  usage, and continue. A late valid invoice replaces its reservation exactly
  once. Runtime timeouts without a usable fallback count as product failures;
  transport failures count as infrastructure errors. Preserve normal runtime
  responses and typed/prose scoring when they are available.
- Unexpected research routing is a failed case; the allowlist blocks its paid
  dispatch. The 14 no-new-facts cases require zero attempted research sends.
- Retain normal production step/output settings. The one-send cap is an explicit
  **measurement restriction**. A denied retry fails its case; it does not establish production retry behavior.
- Nine discovery cases may use the separate Search API. Permit only those case
  IDs, retain separate request/cost accounting, and include their spend in $15.

The [sanctioned live runner](../../../../tests/evals/test_measurement_eval_live.py)
installs the [budget guard](../../../../tests/evals/measurement_budget.py) before
case execution. It uses a shared thread-safe ledger below HTTP retries, plus an
Agent application-request guard. Sync and async sends, streamed usage, judges
and fallback calls are counted. Raw Agent invoices are settled even when the
answer cannot be parsed. Search charges remain separately identified at their
documented per-request rate. The normal scorecard's OpenRouter totals alone are
not the whole bill. Budget exhaustion writes durable partial evidence and
aborts before the ordinary scorecard writer; it never yields a green scorecard.
Completed runs may still have reserved, unbilled calls, reported explicitly as
`accounting_complete=false`. Unknown bills never become zero spend.

The next run starts all 93 cases from scratch and automatically imports the
[stopped run ledger](measurement-aaf05285/cost-events.jsonl): $0.093172736 settled
plus $0.10 reserved, for $0.193172736 already committed against the $15 total.
The prior ledger is immutable and its path is not reused. Paid execution waits
for the founder to free the paid slot.

## Scope

The suite contains 93 cases, 106 turn opportunities including follow-ups, and 47
logical prose judgments. Judge fallback/transport costs count toward the budget.

Agent-eligible case IDs (eligibility does not require a call):

```text
calculation_followups_q5_no_personal_product_pick_en
calculation_followups_q5_no_personal_product_pick_es_419
calculation_followups_q10_historical_drawdown_en
calculation_followups_q10_historical_drawdown_es_419
calculation_followups_q10_generic_crypto_en
calculation_followups_q10_generic_crypto_es_419
calculation_followups_new_external_fact_en
calculation_followups_new_external_fact_es_419
capability_honesty_future_performance_nvda_golden_cross
capability_honesty_future_performance_btc_regression
messy_spanish_future_performance_nvda_cruce_dorado
ordinary_conversation_concept_compound_interest_en
ordinary_conversation_concept_inflation_es
ordinary_conversation_concept_etf_es
ordinary_conversation_macro_curiosity_en
ordinary_conversation_price_question_en
```

Search/discovery case IDs:

```text
asset_discovery_category_english_issue_244
asset_discovery_peer_anchor_english_issue_244
asset_discovery_comparison_anchor_english_issue_244
asset_discovery_category_spanish_issue_244
asset_discovery_recent_ipo_exact_issue_344
asset_discovery_trending_crypto_exact_issue_344
asset_discovery_old_pharma_escalation_exact_issue_344
asset_discovery_semantic_pharma_escalation_issue_344
asset_discovery_spanish_generated_pharma_escalation_issue_344
```

Cases requiring no new facts and zero research attempts:

```text
calculation_followups_q2_card_recall_en
calculation_followups_q2_card_recall_es_419
calculation_followups_q3_periods_and_profile_currency_en
calculation_followups_q3_periods_and_profile_currency_es_419
calculation_followups_q4_changed_principal_en
calculation_followups_q4_changed_principal_es_419
calculation_followups_q5_rewards_fill_en
calculation_followups_q5_rewards_fill_es_419
calculation_followups_q7_conversion_fill_en
calculation_followups_q7_conversion_fill_es_419
calculation_followups_q7_changed_goal_risk_en
calculation_followups_q7_changed_goal_risk_es_419
calculation_followups_explain_prior_answer_en
calculation_followups_explain_prior_answer_es_419
```
