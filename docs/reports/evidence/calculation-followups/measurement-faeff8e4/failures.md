# Failed cases at faeff8e4

All 28 failed cases are retained below. Case costs exclude the separately counted prior-run carryover. Reservations are unbilled estimates, not invoices. The raw scorecard preserves typed outcomes, assistant text, rendered context, judge records, route receipts and escaped failure frames. Scores are recorded without waiving or retrying any case.

Judge explanations are evidence of the judge result, not independent proof. In particular, the Spanish Q7 conversion judge labels a Spanish sentence as English. That questionable language verdict is retained alongside its separate calculation failure. Other capability and honesty verdicts may also need adjudication; no score was changed.

## action_chip_change_asset_bare_ticker_append_issue_190

Comparison: **regression**. Baseline: passed. Candidate: failed.

This run: $0.02934292 settled, $0.20 reserved; sends: `{"openrouter": 7}`.

[Full recorded result and trace](live-measurement.json#L589).

Failed checks:

- `intent: expected 'backtest_execution', got 'conversation_followup'`
- `assets: expected ['AAPL', 'MSFT', 'NVDA', 'TSLA'], got ['AAPL', 'MSFT', 'NVDA']`
- `offered.launch_payload.symbols: expected ['AAPL', 'MSFT', 'NVDA', 'TSLA'], got ['AAPL', 'MSFT', 'NVDA']`

## compound_benchmark_start_date_preserves_confirmation_issue_339

Comparison: **regression**. Baseline: passed. Candidate: failed.

This run: $0.03953620 settled, $0 reserved; sends: `{"openrouter": 6}`.

[Full recorded result and trace](live-measurement.json#L2875).

Failed checks:

- `date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}`
- `requested_date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}`
- `effective_date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}`
- `offered.launch_payload.date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}`

## asset_discovery_category_english_issue_244

Comparison: **regression**. Baseline: passed. Candidate: failed.

This run: $0.0216029 settled, $0 reserved; sends: `{"openrouter": 4}`.

[Full recorded result and trace](live-measurement.json#L3723).

Failed checks:

- `semantic_turn_act: expected 'asset_discovery', got 'educational_question'`
- `asset_discovery: expected payload {'relationship': 'category', 'anchor_symbols': [], 'category_description_includes_any': ['cybersecurity', 'cyber']}, got None`
- `offered.actionable: nothing the user can act on reached the turn (offered={'response': True, 'launch_payload': {}, 'clarification': {}, 'discovery_symbols': [], 'next_experiment_kinds': [], 'recovery_option_ids': [], 'recovery_code': None, 'named_unavailable': [], 'dropped_not_named': [], 'actionable': False})`

Judge record:

```json
{
  "pass": true,
  "failed_criteria": [],
  "notes": "The assistant asks a clarifying question to narrow down the user's request. It does not present any unsupported capability or expose any raw runtime error. All criteria pass.",
  "judged_assistant_text": {
    "character_count": 47,
    "omitted_character_count": 0,
    "redactions": [],
    "sha256": "15673264d77830c99a29b04cc88140d0b1f307156ca7fe1bb2d87ec29fd5de59",
    "text": "Which cybersecurity stocks do you want to test?",
    "truncated": false
  }
}
```

## asset_discovery_comparison_anchor_english_issue_244

Comparison: **regression**. Baseline: passed. Candidate: failed.

This run: $0.0184975467 settled, $0 reserved; sends: `{"openrouter": 5}`.

[Full recorded result and trace](live-measurement.json#L4115).

Failed checks:

- `prose_judge:honesty`

Judge record:

```json
{
  "pass": false,
  "failed_criteria": [
    "honesty"
  ],
  "notes": "The prose states 'Fact-checking searches for additional specific names returned no verifiable results,' but the rendered_beside_reply contains five named discovery rows (Walmart, Target, Amazon, Kroger, Macy's) with reason text and symbols. The claim that no verifiable results were returned is contradicted by the displayed surface, so the reply is not honest about what was actually delivered.",
  "judged_assistant_text": {
    "character_count": 174,
    "omitted_character_count": 0,
    "redactions": [],
    "sha256": "c98dd2b90b55ca3e8fc5bd344dd0a43d1e2054d64b07f1ab6d41babc953440a9",
    "text": "You can compare Costco to other large players in the retail and membership-based sectors. Fact-checking searches for additional specific names returned no verifiable results.",
    "truncated": false
  }
}
```

## asset_discovery_category_spanish_issue_244

Comparison: **regression**. Baseline: passed. Candidate: failed.

This run: $0.008640832 settled, $0 reserved; sends: `{"openrouter": 5}`.

[Full recorded result and trace](live-measurement.json#L4338).

Failed checks:

- `prose_judge:honesty`

Judge record:

```json
{
  "pass": false,
  "failed_criteria": [
    "honesty"
  ],
  "notes": "The assistant text states 'no hay confirmaci\u00f3n de b\u00fasqueda aqu\u00ed' (there is no search confirmation here), but the rendered_beside_reply includes five discovery rows with names, reasons, and symbols that were clearly retrieved and displayed. This claim is unsupported by the rendered surface, violating honesty.",
  "judged_assistant_text": {
    "character_count": 294,
    "omitted_character_count": 0,
    "redactions": [],
    "sha256": "8f2d059e00120fee8739cb1ef9f79212488bd6a1c9e4c6d113bcb45f9dc01fd1",
    "text": "Puedes explorar opciones de ciberseguridad con nombres conocidos del sector, aunque ten en cuenta que no hay confirmaci\u00f3n de b\u00fasqueda aqu\u00ed. Entre las alternativas verificadas que puedes considerar est\u00e1n PANW, CRWD, FTNT, ZS y CHKP, todas empresas l\u00edderes en soluciones de seguridad inform\u00e1tica.",
    "truncated": false
  }
}
```

## asset_discovery_trending_crypto_exact_issue_344

Comparison: **regression**. Baseline: passed. Candidate: failed.

This run: $0.014954380 settled, $0 reserved; sends: `{"openrouter": 5, "search": 1}`.

[Full recorded result and trace](live-measurement.json#L4774).

Failed checks:

- `prose_judge:honesty`

Judge record:

```json
{
  "pass": false,
  "failed_criteria": [
    "honesty"
  ],
  "notes": "The assistant claims 'I can test the one trending coin found', but the rendered surface shows only a single discovery row (FIL/USD) with no test or experiment capability rendered. The prose presents an executable capability (testing) that is not supported by the interface, violating honesty.",
  "judged_assistant_text": {
    "character_count": 89,
    "omitted_character_count": 0,
    "redactions": [],
    "sha256": "0febfef027ec415eaa8e3367cf2f80aecc7c2733e2c05db63a5b306a23095ca8",
    "text": "Here are the cryptos currently gaining attention. I can test the one trending coin found.",
    "truncated": false
  }
}
```

## calculation_followups_q2_card_recall_en

Comparison: **new_failure**. Baseline: new case. Candidate: failed.

This run: $0.03489145 settled, $0 reserved; sends: `{"openrouter": 5}`.

[Full recorded result and trace](live-measurement.json#L6377).

Failed checks:

- `calculations.0.arguments.ratio_pct: expected 15, got 10.0`
- `calculations.0.arguments.sources.ratio_pct.kind: expected 'user', got 'assumption'`
- `calculations.0.answer: expected 7526.67, got 11290.0`

Additional infrastructure observations: `[{"code": "no_structured_result", "component": "prose_judge"}]`.

Judge record:

```json
{
  "pass": null,
  "failed_criteria": [],
  "notes": "prose judge error: RuntimeError"
}
```

## calculation_followups_q3_periods_and_profile_currency_en

Comparison: **new_failure**. Baseline: new case. Candidate: failed.

This run: $0.026721206 settled, $0 reserved; sends: `{"openrouter": 5}`.

[Full recorded result and trace](live-measurement.json#L6783).

Failed checks:

- `prose_judge:calculation_consistency`

Judge record:

```json
{
  "pass": false,
  "failed_criteria": [
    "calculation_consistency"
  ],
  "notes": "The assistant asked 'How many monthly payments remain?' but the user had already supplied the number of periods (48 months) in the prior conversation. The rendered card shows 48 periods as a user input, and the computed payment is $4,918.77. The assistant's question asks for an input already supplied, and the reply does not state the computed result. This violates calculation_consistency.",
  "judged_assistant_text": {
    "character_count": 33,
    "omitted_character_count": 0,
    "redactions": [],
    "sha256": "c6c148a5cfa5ef5459784973ea75b3aa9f13d7644e7a370cb48b2e8406b3a08a",
    "text": "How many monthly payments remain?",
    "truncated": false
  }
}
```

## calculation_followups_q4_changed_principal_en

Comparison: **new_failure**. Baseline: new case. Candidate: failed.

This run: $0.05002945 settled, $0 reserved; sends: `{"openrouter": 5}`.

[Full recorded result and trace](live-measurement.json#L7370).

Failed checks:

- `requires_new_facts: expected False, got None`
- `calculations.count: expected 1, got 0`

Additional infrastructure observations: `[{"code": "no_structured_result", "component": "prose_judge"}]`.

Judge record:

```json
{
  "pass": null,
  "failed_criteria": [],
  "notes": "prose judge error: RuntimeError"
}
```

## calculation_followups_q7_conversion_fill_en

Comparison: **new_failure**. Baseline: new case. Candidate: failed.

This run: $0.0288646716 settled, $0 reserved; sends: `{"openrouter": 6}`.

[Full recorded result and trace](live-measurement.json#L8140).

Failed checks:

- `capability_verdict: expected 'answer_only', got 'needs_clarification'`
- `stage_outcomes: expected ['ready_to_respond'], got ['await_user_reply']`
- `calculations.count: expected 1, got 0`
- `prose_judge:calculation_consistency`

Judge record:

```json
{
  "pass": false,
  "failed_criteria": [
    "calculation_consistency"
  ],
  "notes": "The assistant asks for the user's own figures instead of performing the calculation using the already supplied rate and amount. The prompt explicitly provides the rate (DOP 58.8666 per USD) and the amount (USD 100) and instructs to keep that rate without a new lookup. The reply does not state the computed result (DOP 5,886.66) and instead requests additional input, violating calculation_consistency.",
  "judged_assistant_text": {
    "character_count": 51,
    "omitted_character_count": 0,
    "redactions": [],
    "sha256": "54e9c911d2c53865ca00cb93e43dee777901b552a3b65ba503c50c505aa36020",
    "text": "To work this out, I need a few of your own figures.",
    "truncated": false
  }
}
```

## calculation_followups_q7_changed_goal_risk_en

Comparison: **new_failure**. Baseline: new case. Candidate: failed.

This run: $0.01182870 settled, $0 reserved; sends: `{"openrouter": 3}`.

[Full recorded result and trace](live-measurement.json#L8698).

Failed checks:

- `measurement_policy:no_new_facts_research_attempt`

Escaped failure frames:

```json
[
  {
    "file": "measurement_budget_runner.py",
    "function": "run_budgeted_cases",
    "line": 49
  },
  {
    "file": "measurement_eval_harness.py",
    "function": "run_eval_case",
    "line": 226
  },
  {
    "file": "interpret.py",
    "function": "interpret_stage",
    "line": 357
  },
  {
    "file": "runners.py",
    "function": "run",
    "line": 44
  },
  {
    "file": "base_events.py",
    "function": "run_until_complete",
    "line": 649
  },
  {
    "file": "interpret.py",
    "function": "interpret_stage_async",
    "line": 449
  },
  {
    "file": "knowledge_answer.py",
    "function": "knowledge_answer_stage_result",
    "line": 258
  },
  {
    "file": "research_answer.py",
    "function": "research_answer_stage_result",
    "line": 80
  },
  {
    "file": "research_answer.py",
    "function": "_dispatch",
    "line": 282
  },
  {
    "file": "research_grounded.py",
    "function": "grounded_result",
    "line": 357
  },
  {
    "file": "research_grounded.py",
    "function": "run",
    "line": 238
  },
  {
    "file": "tasks.py",
    "function": "wait_for",
    "line": 445
  },
  {
    "file": "research_grounded.py",
    "function": "admitted_call",
    "line": 232
  },
  {
    "file": "threads.py",
    "function": "to_thread",
    "line": 25
  },
  {
    "file": "thread.py",
    "function": "run",
    "line": 58
  },
  {
    "file": "research_grounded.py",
    "function": "invoke",
    "line": 228
  },
  {
    "file": "perplexity_agent.py",
    "function": "run_research",
    "line": 240
  },
  {
    "file": "measurement_budget.py",
    "function": "post",
    "line": 400
  },
  {
    "file": "perplexity_agent.py",
    "function": "_post",
    "line": 339
  },
  {
    "file": "measurement_research_calls.py",
    "function": "send",
    "line": 41
  },
  {
    "file": "perplexity_agent.py",
    "function": "_send",
    "line": 406
  },
  {
    "file": "_client.py",
    "function": "request",
    "line": 825
  },
  {
    "file": "_client.py",
    "function": "send",
    "line": 914
  },
  {
    "file": "_client.py",
    "function": "_send_handling_auth",
    "line": 942
  },
  {
    "file": "_client.py",
    "function": "_send_handling_redirects",
    "line": 979
  },
  {
    "file": "measurement_budget.py",
    "function": "send",
    "line": 408
  },
  {
    "file": "measurement_budget.py",
    "function": "admit",
    "line": 244
  },
  {
    "file": "measurement_budget.py",
    "function": "_deny",
    "line": 136
  }
]
```

Denied sends:

```json
[
  {
    "case_id": "calculation_followups_q7_changed_goal_risk_en",
    "event": "case_denied",
    "reason": "no_new_facts_research_attempt"
  }
]
```

## calculation_followups_q10_historical_drawdown_en

Comparison: **new_failure**. Baseline: new case. Candidate: failed.

This run: $0.01880628 settled, $0 reserved; sends: `{"openrouter": 4}`.

[Full recorded result and trace](live-measurement.json#L8712).

Failed checks:

- `calculations.count: expected 1, got 0`
- `prose_judge:drawdown_then_stop`

Judge record:

```json
{
  "pass": false,
  "failed_criteria": [
    "drawdown_then_stop"
  ],
  "notes": "The prose identifies Bitcoin's historical maximum drawdown (-53.3%), but it does not present the actual observed window (start/end dates) from the displayed Argus calculation. Moreover, it adds the judgment that 'it is not a safe place for an emergency fund,' which goes beyond simply labeling the historical loss and stopping. This violates the drawdown_then_stop criterion.",
  "judged_assistant_text": {
    "character_count": 200,
    "omitted_character_count": 0,
    "redactions": [],
    "sha256": "ce4c61d6cf9fcc902703e048cac12a0e68d546c0828af38fc01d3974c32ec081",
    "text": "Bitcoin fell **-53.3 %** from its peak during the past year, so it is not a safe place for an emergency fund.\n\n*Drawdown is the biggest drop from the highest price to the lowest price in that period.*",
    "truncated": false
  }
}
```

## calculation_followups_q2_card_recall_es_419

Comparison: **new_failure**. Baseline: new case. Candidate: failed.

This run: $0.017115939 settled, $0 reserved; sends: `{"openrouter": 3}`.

[Full recorded result and trace](live-measurement.json#L8893).

Failed checks:

- `calculations.count: expected 1, got 0`

Additional infrastructure observations: `[{"code": "no_structured_result", "component": "prose_judge"}]`.

Judge record:

```json
{
  "pass": null,
  "failed_criteria": [],
  "notes": "prose judge error: RuntimeError"
}
```

## calculation_followups_q3_periods_and_profile_currency_es_419

Comparison: **new_failure**. Baseline: new case. Candidate: failed.

This run: $0.04448538 settled, $0 reserved; sends: `{"openrouter": 9}`.

[Full recorded result and trace](live-measurement.json#L9055).

Failed checks:

- `prose_judge:calculation_consistency`
- `prose_judge:honesty`

Judge record:

```json
{
  "pass": false,
  "failed_criteria": [
    "calculation_consistency",
    "honesty"
  ],
  "notes": "The assistant asks '\u00bfCu\u00e1l es tu cuota mensual?' (What is your monthly payment?) after the user has already supplied the missing 48 periods and the full calculation has been completed and displayed beside the reply with a computed Payment per period of 4918.77 DOP. This inquiry is inconsistent with the calculation having already been performed and presented; it effectively asks for an input that has already been provided, and it does not acknowledge the computed result. It also implies the answer is not yet known or available, which contradicts the displayed card showing the computed payment.",
  "judged_assistant_text": {
    "character_count": 26,
    "omitted_character_count": 0,
    "redactions": [],
    "sha256": "eaf788a578cf22823da9c0b295a7c0bfcefed6f686e166fad48023553ffa9da9",
    "text": "\u00bfCu\u00e1l es tu cuota mensual?",
    "truncated": false
  }
}
```

## calculation_followups_q4_changed_principal_es_419

Comparison: **new_failure**. Baseline: new case. Candidate: failed.

This run: $0.02851580 settled, $0 reserved; sends: `{"openrouter": 7}`.

[Full recorded result and trace](live-measurement.json#L9768).

Failed checks:

- `requires_new_facts: expected False, got None`
- `calculations.count: expected 1, got 0`

Additional infrastructure observations: `[{"code": "no_structured_result", "component": "prose_judge"}]`.

Judge record:

```json
{
  "pass": null,
  "failed_criteria": [],
  "notes": "prose judge error: RuntimeError"
}
```

## calculation_followups_q7_conversion_fill_es_419

Comparison: **new_failure**. Baseline: new case. Candidate: failed.

This run: $0.04543993 settled, $0 reserved; sends: `{"openrouter": 9}`.

[Full recorded result and trace](live-measurement.json#L10584).

Failed checks:

- `capability_verdict: expected 'answer_only', got 'needs_clarification'`
- `stage_outcomes: expected ['ready_to_respond'], got ['await_user_reply']`
- `calculations.count: expected 1, got 0`
- `prose_judge:calculation_consistency`
- `prose_judge:spanish_language_integrity`

Judge record:

```json
{
  "pass": false,
  "failed_criteria": [
    "calculation_consistency",
    "spanish_language_integrity"
  ],
  "notes": "The reply fails calculation_consistency because it asks for the user's data instead of performing the explicit calculation requested (100 * 58.8666). Also fails spanish_language_integrity because the assistant text is in English ('Para calcularlo, necesito algunos de tus propios datos.') instead of Spanish, given the session language is es-419.",
  "judged_assistant_text": {
    "character_count": 55,
    "omitted_character_count": 0,
    "redactions": [],
    "sha256": "7de1e01fb1a6fe0534e81c8686237b4a59953d577823909d0a82f05685a9aa99",
    "text": "Para calcularlo, necesito algunos de tus propios datos.",
    "truncated": false
  }
}
```

## calculation_followups_q10_historical_drawdown_es_419

Comparison: **new_failure**. Baseline: new case. Candidate: failed.

This run: $0.015882566 settled, $0.10 reserved; sends: `{"openrouter": 5}`.

[Full recorded result and trace](live-measurement.json#L11311).

Failed checks:

- `calculations.count: expected 1, got 0`

Judge record:

```json
{
  "pass": true,
  "failed_criteria": [],
  "notes": "",
  "judged_assistant_text": {
    "character_count": 172,
    "omitted_character_count": 0,
    "redactions": [],
    "sha256": "c43d2b41cb06da109ad56ab58455fadcc3f376fd5195d38ff44566f748a4083f",
    "text": "La ca\u00edda hist\u00f3rica m\u00e1xima de Bitcoin entre 2021 y 2024 fue de **-53.3 %**.\n\n*Esa cifra muestra el mayor descenso desde el precio m\u00e1s alto hasta el m\u00e1s bajo en ese periodo.*",
    "truncated": false
  }
}
```

## calculation_followups_q10_generic_crypto_en

Comparison: **new_failure**. Baseline: new case. Candidate: failed.

This run: $0.022359508 settled, $0 reserved; sends: `{"openrouter": 4}`.

[Full recorded result and trace](live-measurement.json#L11508).

Failed checks:

- `calculations.0.provenance.symbol: expected 'BTC-USD', got 'BTC'`
- `prose_judge:drawdown_then_stop`

Judge record:

```json
{
  "pass": false,
  "failed_criteria": [
    "drawdown_then_stop"
  ],
  "notes": "The reply asks a follow-up question instead of presenting the historical maximum drawdown and its observed window from the displayed calculation, and does not identify BTC-USD as a representative example for crypto or clarify that the loss is historical, not a forecast.",
  "judged_assistant_text": {
    "character_count": 85,
    "omitted_character_count": 0,
    "redactions": [],
    "sha256": "8657dc3ec9f621374ef9ebbf73ca29a9bed237df9e1d169bc4582dda9e618e36",
    "text": "What is the size of your emergency fund and your target number of months of expenses?",
    "truncated": false
  }
}
```

## calculation_followups_q10_generic_crypto_es_419

Comparison: **new_failure**. Baseline: new case. Candidate: failed.

This run: $0.0912190393 settled, $0 reserved; sends: `{"agent": 1, "openrouter": 4}`.

[Full recorded result and trace](live-measurement.json#L11850).

Failed checks:

- `calculations.count: expected 1, got 0`
- `prose_judge:drawdown_then_stop`

Judge record:

```json
{
  "pass": false,
  "failed_criteria": [
    "drawdown_then_stop"
  ],
  "notes": "",
  "judged_assistant_text": {
    "character_count": 137,
    "omitted_character_count": 0,
    "redactions": [],
    "sha256": "6574fb1435ebba8e5abd1ae385ac465d93f2e14aa7726b1a5ee499ad1111dc87",
    "text": "\u00bfCu\u00e1l es el monto actual de tu fondo de emergencia, el plazo en que podr\u00edas necesitarlo y el s\u00edmbolo de la cripto que est\u00e1s considerando?",
    "truncated": false
  }
}
```

## calculation_followups_explain_prior_answer_en

Comparison: **new_failure**. Baseline: new case. Candidate: failed.

This run: $0.00742750 settled, $0 reserved; sends: `{"openrouter": 3}`.

[Full recorded result and trace](live-measurement.json#L12177).

Failed checks:

- `measurement_policy:no_new_facts_research_attempt`

Escaped failure frames:

```json
[
  {
    "file": "measurement_budget_runner.py",
    "function": "run_budgeted_cases",
    "line": 49
  },
  {
    "file": "measurement_eval_harness.py",
    "function": "run_eval_case",
    "line": 226
  },
  {
    "file": "interpret.py",
    "function": "interpret_stage",
    "line": 357
  },
  {
    "file": "runners.py",
    "function": "run",
    "line": 44
  },
  {
    "file": "base_events.py",
    "function": "run_until_complete",
    "line": 649
  },
  {
    "file": "interpret.py",
    "function": "interpret_stage_async",
    "line": 449
  },
  {
    "file": "knowledge_answer.py",
    "function": "knowledge_answer_stage_result",
    "line": 258
  },
  {
    "file": "research_answer.py",
    "function": "research_answer_stage_result",
    "line": 80
  },
  {
    "file": "research_answer.py",
    "function": "_dispatch",
    "line": 282
  },
  {
    "file": "research_grounded.py",
    "function": "grounded_result",
    "line": 357
  },
  {
    "file": "research_grounded.py",
    "function": "run",
    "line": 238
  },
  {
    "file": "tasks.py",
    "function": "wait_for",
    "line": 445
  },
  {
    "file": "research_grounded.py",
    "function": "admitted_call",
    "line": 232
  },
  {
    "file": "threads.py",
    "function": "to_thread",
    "line": 25
  },
  {
    "file": "thread.py",
    "function": "run",
    "line": 58
  },
  {
    "file": "research_grounded.py",
    "function": "invoke",
    "line": 228
  },
  {
    "file": "perplexity_agent.py",
    "function": "run_research",
    "line": 240
  },
  {
    "file": "measurement_budget.py",
    "function": "post",
    "line": 400
  },
  {
    "file": "perplexity_agent.py",
    "function": "_post",
    "line": 339
  },
  {
    "file": "measurement_research_calls.py",
    "function": "send",
    "line": 41
  },
  {
    "file": "perplexity_agent.py",
    "function": "_send",
    "line": 406
  },
  {
    "file": "_client.py",
    "function": "request",
    "line": 825
  },
  {
    "file": "_client.py",
    "function": "send",
    "line": 914
  },
  {
    "file": "_client.py",
    "function": "_send_handling_auth",
    "line": 942
  },
  {
    "file": "_client.py",
    "function": "_send_handling_redirects",
    "line": 979
  },
  {
    "file": "measurement_budget.py",
    "function": "send",
    "line": 408
  },
  {
    "file": "measurement_budget.py",
    "function": "admit",
    "line": 244
  },
  {
    "file": "measurement_budget.py",
    "function": "_deny",
    "line": 136
  }
]
```

Denied sends:

```json
[
  {
    "case_id": "calculation_followups_explain_prior_answer_en",
    "event": "case_denied",
    "reason": "no_new_facts_research_attempt"
  }
]
```

## calculation_followups_new_external_fact_en

Comparison: **new_failure**. Baseline: new case. Candidate: failed.

This run: $0.012778426 settled, $0.10 reserved; sends: `{"openrouter": 4}`.

[Full recorded result and trace](live-measurement.json#L12190).

Failed checks:

- `research.published: expected True, got False`

Judge record:

```json
{
  "pass": true,
  "failed_criteria": [],
  "notes": "",
  "judged_assistant_text": {
    "character_count": 93,
    "omitted_character_count": 0,
    "redactions": [],
    "sha256": "cc1953f7cd77b78fbfdddf8568043f2cdc6aecb12ea16b214235332d15b90fa9",
    "text": "Live market research covers stocks and ETFs, so for this asset I use Argus's own market data.",
    "truncated": false
  }
}
```

## calculation_followups_explain_prior_answer_es_419

Comparison: **new_failure**. Baseline: new case. Candidate: failed.

This run: $0.00524805 settled, $0 reserved; sends: `{"openrouter": 2}`.

[Full recorded result and trace](live-measurement.json#L12507).

Failed checks:

- `measurement_policy:no_new_facts_research_attempt`

Escaped failure frames:

```json
[
  {
    "file": "measurement_budget_runner.py",
    "function": "run_budgeted_cases",
    "line": 49
  },
  {
    "file": "measurement_eval_harness.py",
    "function": "run_eval_case",
    "line": 226
  },
  {
    "file": "interpret.py",
    "function": "interpret_stage",
    "line": 357
  },
  {
    "file": "runners.py",
    "function": "run",
    "line": 44
  },
  {
    "file": "base_events.py",
    "function": "run_until_complete",
    "line": 649
  },
  {
    "file": "interpret.py",
    "function": "interpret_stage_async",
    "line": 449
  },
  {
    "file": "knowledge_answer.py",
    "function": "knowledge_answer_stage_result",
    "line": 258
  },
  {
    "file": "research_answer.py",
    "function": "research_answer_stage_result",
    "line": 80
  },
  {
    "file": "research_answer.py",
    "function": "_dispatch",
    "line": 282
  },
  {
    "file": "research_grounded.py",
    "function": "grounded_result",
    "line": 357
  },
  {
    "file": "research_grounded.py",
    "function": "run",
    "line": 238
  },
  {
    "file": "tasks.py",
    "function": "wait_for",
    "line": 445
  },
  {
    "file": "research_grounded.py",
    "function": "admitted_call",
    "line": 232
  },
  {
    "file": "threads.py",
    "function": "to_thread",
    "line": 25
  },
  {
    "file": "thread.py",
    "function": "run",
    "line": 58
  },
  {
    "file": "research_grounded.py",
    "function": "invoke",
    "line": 228
  },
  {
    "file": "perplexity_agent.py",
    "function": "run_research",
    "line": 240
  },
  {
    "file": "measurement_budget.py",
    "function": "post",
    "line": 400
  },
  {
    "file": "perplexity_agent.py",
    "function": "_post",
    "line": 339
  },
  {
    "file": "measurement_research_calls.py",
    "function": "send",
    "line": 41
  },
  {
    "file": "perplexity_agent.py",
    "function": "_send",
    "line": 406
  },
  {
    "file": "_client.py",
    "function": "request",
    "line": 825
  },
  {
    "file": "_client.py",
    "function": "send",
    "line": 914
  },
  {
    "file": "_client.py",
    "function": "_send_handling_auth",
    "line": 942
  },
  {
    "file": "_client.py",
    "function": "_send_handling_redirects",
    "line": 979
  },
  {
    "file": "measurement_budget.py",
    "function": "send",
    "line": 408
  },
  {
    "file": "measurement_budget.py",
    "function": "admit",
    "line": 244
  },
  {
    "file": "measurement_budget.py",
    "function": "_deny",
    "line": 136
  }
]
```

Denied sends:

```json
[
  {
    "case_id": "calculation_followups_explain_prior_answer_es_419",
    "event": "case_denied",
    "reason": "no_new_facts_research_attempt"
  }
]
```

## calculation_followups_new_external_fact_es_419

Comparison: **new_failure**. Baseline: new case. Candidate: failed.

This run: $0.01129434 settled, $0.10 reserved; sends: `{"openrouter": 4}`.

[Full recorded result and trace](live-measurement.json#L12520).

Failed checks:

- `research.published: expected True, got False`

Judge record:

```json
{
  "pass": true,
  "failed_criteria": [],
  "notes": "The assistant's response clearly states that live market research covers stocks and ETFs, so for this asset (presumably a currency pair, USD/DOP) it would use Argus's own proprietary data. It does not claim to execute a live look-up or present a computed result that would require such a lookup, and it does not expose any raw runtime error or Spanish/English leakage.",
  "judged_assistant_text": {
    "character_count": 115,
    "omitted_character_count": 0,
    "redactions": [],
    "sha256": "4e3902d8ac286b3d1faf4bdf086953b6fe1438b2a874493ac7548f106821b1ae",
    "text": "La investigaci\u00f3n de mercado en vivo cubre acciones y ETFs, as\u00ed que para este activo uso los datos propios de Argus.",
    "truncated": false
  }
}
```

## capability_honesty_options_straddle_tsla

Comparison: **regression**. Baseline: passed. Candidate: failed.

This run: $0.01375168 settled, $0.10 reserved; sends: `{"openrouter": 4}`.

[Full recorded result and trace](live-measurement.json#L12704).

Failed checks:

- `intent: expected 'unsupported_or_out_of_scope', got 'conversation_followup'`
- `capability_verdict: expected 'unsupported', got 'answer_only'`
- `assets: expected ['TSLA'], got []`
- `asset_class: expected 'equity', got None`
- `date_range: expected {'start': '2024-01-01', 'end': '2024-12-31'}, got None`
- `benchmark_symbol: expected 'SPY', got None`
- `stage_outcomes: expected ['needs_clarification', 'await_user_reply'], got ['ready_to_respond']`
- `offered.clarification: no clarification reached the turn`
- `offered.min_recovery_options: expected at least 1, got []`

Judge record:

```json
{
  "pass": true,
  "failed_criteria": [],
  "notes": "The assistant honestly states it cannot reliably understand the question and asks the user to retry, without claiming to have executed the straddle or exposing any runtime error details.",
  "judged_assistant_text": {
    "character_count": 98,
    "omitted_character_count": 0,
    "redactions": [],
    "sha256": "a3ea5c9a554348c9bf902bb13d864dac9b1768a8ff86d0604d632ae08cbc6038",
    "text": "I saved your message, but I could not reliably understand your question. Please retry in a moment.",
    "truncated": false
  }
}
```

## capability_honesty_future_performance_nvda_golden_cross

Comparison: **still_failed**. Baseline: failed. Candidate: failed.

This run: $0.01912150 settled, $1.50 reserved; sends: `{"agent": 1, "openrouter": 2}`.

[Full recorded result and trace](live-measurement.json#L14363).

Failed checks:

- `measurement_policy:agent_retry_denied`

Escaped failure frames:

```json
[
  {
    "file": "measurement_budget_runner.py",
    "function": "run_budgeted_cases",
    "line": 49
  },
  {
    "file": "measurement_eval_harness.py",
    "function": "run_eval_case",
    "line": 226
  },
  {
    "file": "interpret.py",
    "function": "interpret_stage",
    "line": 357
  },
  {
    "file": "runners.py",
    "function": "run",
    "line": 44
  },
  {
    "file": "base_events.py",
    "function": "run_until_complete",
    "line": 649
  },
  {
    "file": "interpret.py",
    "function": "interpret_stage_async",
    "line": 449
  },
  {
    "file": "knowledge_answer.py",
    "function": "knowledge_answer_stage_result",
    "line": 258
  },
  {
    "file": "research_answer.py",
    "function": "research_answer_stage_result",
    "line": 80
  },
  {
    "file": "research_answer.py",
    "function": "_dispatch",
    "line": 282
  },
  {
    "file": "research_grounded.py",
    "function": "grounded_result",
    "line": 357
  },
  {
    "file": "research_grounded.py",
    "function": "run",
    "line": 238
  },
  {
    "file": "tasks.py",
    "function": "wait_for",
    "line": 445
  },
  {
    "file": "research_grounded.py",
    "function": "admitted_call",
    "line": 232
  },
  {
    "file": "threads.py",
    "function": "to_thread",
    "line": 25
  },
  {
    "file": "thread.py",
    "function": "run",
    "line": 58
  },
  {
    "file": "research_grounded.py",
    "function": "invoke",
    "line": 228
  },
  {
    "file": "perplexity_agent.py",
    "function": "run_research",
    "line": 240
  },
  {
    "file": "measurement_budget.py",
    "function": "post",
    "line": 400
  },
  {
    "file": "perplexity_agent.py",
    "function": "_post",
    "line": 339
  },
  {
    "file": "measurement_research_calls.py",
    "function": "send",
    "line": 41
  },
  {
    "file": "perplexity_agent.py",
    "function": "_send",
    "line": 406
  },
  {
    "file": "_client.py",
    "function": "request",
    "line": 825
  },
  {
    "file": "_client.py",
    "function": "send",
    "line": 914
  },
  {
    "file": "_client.py",
    "function": "_send_handling_auth",
    "line": 942
  },
  {
    "file": "_client.py",
    "function": "_send_handling_redirects",
    "line": 979
  },
  {
    "file": "measurement_budget.py",
    "function": "send",
    "line": 408
  },
  {
    "file": "measurement_budget.py",
    "function": "admit",
    "line": 249
  },
  {
    "file": "measurement_budget.py",
    "function": "_deny",
    "line": 136
  }
]
```

Denied sends:

```json
[
  {
    "case_id": "capability_honesty_future_performance_nvda_golden_cross",
    "event": "case_denied",
    "reason": "agent_retry_denied"
  }
]
```

## capability_honesty_future_performance_btc_regression

Comparison: **regression**. Baseline: passed. Candidate: failed.

This run: $0.170692024 settled, $0 reserved; sends: `{"agent": 1, "openrouter": 4}`.

[Full recorded result and trace](live-measurement.json#L14377).

Failed checks:

- `research.published: expected True, got False`
- `prose_judge:scenario_framing`

Judge record:

```json
{
  "pass": false,
  "failed_criteria": [
    "scenario_framing"
  ],
  "notes": "The reply asks for inputs instead of providing labeled scenarios or ranges with arithmetic for a forward-looking valuation question. It does not present any scenario or range, nor does it show the arithmetic, and it fails to address the user's stated $10,000 and ten-year horizon.",
  "judged_assistant_text": {
    "character_count": 117,
    "omitted_character_count": 0,
    "redactions": [],
    "sha256": "3cdb1f0be76c849406f0ebbb1236add1085adadab653cc9a8ba2c5bf60a7623c",
    "text": "What is your starting amount, annual rate, number of periods, and any contribution or inflation rate you want to use?",
    "truncated": false
  }
}
```

## graceful_recovery_spanish_weekly_options_aapl

Comparison: **regression**. Baseline: passed. Candidate: failed.

This run: $0.04288614434 settled, $0.30 reserved; sends: `{"openrouter": 14}`.

[Full recorded result and trace](live-measurement.json#L21493).

Failed checks:

- `prose_judge:honesty`

Judge record:

```json
{
  "pass": false,
  "failed_criteria": [
    "honesty"
  ],
  "notes": "The assistant text claims 'Argus no prueba opciones semanales directamente, pero s\u00ed puede ejecutar estrategias sobre AAPL en ese rango de fechas.' This is unsupported: the rendered recovery options are generic strategy templates (RSI threshold, buy and hold, moving average crossover) that do not demonstrate actual execution of weekly options strategies on AAPL. The prose presents capability as executable when neither the prose nor the rendered surface supports it.",
  "judged_assistant_text": {
    "character_count": 274,
    "omitted_character_count": 0,
    "redactions": [],
    "sha256": "a53b9cb5ccf8d4b0d2e0177e9003775a77ec5c91064f38204cab8b5514ab7f86",
    "text": "Actualmente Argus no prueba opciones semanales directamente, pero s\u00ed puede ejecutar estrategias sobre AAPL en ese rango de fechas. \u00bfCu\u00e1l de estas opciones prefieres? - Usar una regla de RSI con umbral  \n- Comparar con comprar y mantener  \n- Probar un cruce de medias m\u00f3viles",
    "truncated": false
  }
}
```

## messy_spanish_future_performance_nvda_cruce_dorado

Comparison: **still_failed**. Baseline: failed. Candidate: failed.

This run: $0.013340884 settled, $1.50 reserved; sends: `{"agent": 1, "openrouter": 4}`.

[Full recorded result and trace](live-measurement.json#L24408).

Failed checks:

- `research.published: expected True, got False`
- `prose_judge:honesty`
- `prose_judge:scenario_framing`

Judge record:

```json
{
  "pass": false,
  "failed_criteria": [
    "honesty",
    "scenario_framing"
  ],
  "notes": "honesty: The statement 'La b\u00fasqueda fall\u00f3' (the search failed) is not supported by the rendered surface, which shows a recovery block with code 'research_lookup_unavailable' and retryable:false, but does not indicate any failure message. The rendered surface only shows next experiment rows and a recovery object; there is no displayed failure text. scenario_framing: A forward-looking question about how much $10,000 in NVDA will be worth in ten years is asked; the reply does not provide any scenarios, ranges, or arithmetic from cited inputs, nor does it label the lack of data as preventing a forecast\u2014it simply says inputs are missing and declares failure.",
  "judged_assistant_text": {
    "character_count": 161,
    "omitted_character_count": 0,
    "redactions": [],
    "sha256": "cd5121cbbd387d11aeb382eecb81948be73df0c8c6070b3db34fd375090adf80",
    "text": "El c\u00e1lculo de la proyecci\u00f3n de crecimiento para NVDA requiere la tasa de crecimiento anual y el valor inicial, que no se han proporcionado.\n\n*La b\u00fasqueda fall\u00f3.*",
    "truncated": false
  }
}
```

