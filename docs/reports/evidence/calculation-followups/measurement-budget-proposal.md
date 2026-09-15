# Proposed 93-case measurement budget

Status: founder-approved budget. The measurement-only guard now enforces the
limits below at the HTTP-send boundary when `ARGUS_EVAL_BUDGET_REPORT` is set.
It leaves production retries unchanged. Live execution still requires its
explicit go and a clean reconciled head; enabling the guard alone starts no call.

## Spending proposal

Use a **$15 monitored stop budget**: $8 for Agent research, $4 for OpenRouter
interpretation/voicing/judges, and $3 reserved for Search and billing uncertainty.
Stop before dispatch when settled spend plus the reservation would exceed the
applicable pool or total. Do not automatically rerun failed cases.

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
  before dispatch. Record a retry-budget failure and stop; never count that case
  as a model-quality pass or silently substitute a cheaper execution path.
- Run serially, with at most one possibly billing Agent request outstanding.
- Reserve $1.50 before each Agent send; settle using the response-owned invoice.
  Stop if the case's actual bill exceeds $1.50, or settled/reserved Agent spend
  reaches $8. Reservations are estimates and can be exceeded by the active call.
- Stop the entire measurement on missing or unpriced usage, or an uncertain
  timeout. Do not send another request while the previous bill is unresolved.
- Unexpected research routing is a failed case; the allowlist blocks its paid
  dispatch. The 14 no-new-facts cases require zero attempted research sends.
- Retain normal production step/output settings. The one-send cap is an explicit
  **measurement restriction**. A run that needs retries is incomplete under this
  budget; it does not establish production retry behavior.
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
