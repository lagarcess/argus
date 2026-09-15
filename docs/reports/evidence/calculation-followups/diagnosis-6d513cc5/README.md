# Free diagnosis of the 28 failures at 6d513cc5

The evidence commit is `6d513cc5055631ece01f0e75bfc293fe81fcf765`; the live runtime was `faeff8e448a22032989895426b06b3a32af781ed`. This diagnosis made **no paid calls** and does not change any measurement score, authored measurement fixture, recorded provider fixture, judge, or freeze fingerprint.

The trace proves one PR-caused guard defect (English Q2). Four other cases expose incomplete wiring of newly added tools. Twelve failures have independent drift evidence, a pre-existing deterministic boundary, or a prior failed baseline. Four have fixture/judge correction proposals. Seven remain causally unresolved. These are 28 mutually exclusive primary labels; several cases also have a secondary judge defect.

A new failing case is not automatically a regression. Likewise, identical code does not prove identical model behavior: the shared schema changed. In particular, the free null-object replay proves that validation defect predates this PR, not that the model would have emitted null at the same rate without the PR. Unresolved cases are not silently assigned to drift or waived.

## Evidence and counterfactual limits

- [Committed measurement and receipts](../measurement-faeff8e4/live-measurement.json), [original failures and costs](../measurement-faeff8e4/failures.md), and [case comparison](../measurement-faeff8e4/case-comparison.json) remain unchanged.
- [Original PR cause hunks](original-cause-hunks.patch) compare reconciled integration `bed233b0cdc96366acc5fc9d5a8d9193723612af` with the failed evidence head. The relevant hunks are `resolve_calculation`'s new prior-input/source gate, its new currency ownership, and the calculation-admission changes. Historical drawdown also adds `src/argus/domain/calculations/historical_drawdown.py`; `research_answer._dispatch` still sent `market_stats` to `_legacy_kind_result` at the measured head.
- [Free baseline replay output](baseline-boundary-replay.txt) uses an archived, unchanged `bed233b0` source tree. It reproduces null-object rejection, acceptance of both Q3 question/card contradictions, the missing-query concept fallback, and an uncovered currency fact returning zero sources. These are boundary counterfactuals, not simulated live model results.
- [Supplemental local diagnostics](supplemental-local-log.json) identify the exact guard/null fields. These lines came from the local pytest log and were not in the original committed scorecard. The committed receipts independently retain the validation failures. Raw provider responses were not retained.
- The founder supplied independent same-week failures for #339, #344, and BTC. [Issue #647](https://github.com/lagarcess/argus/issues/647) owns the independently observed -100% growth rejection. The BTC trace here does not establish that value.

To reproduce the free baseline boundaries, archive only source into an ignored directory, then run the committed helper against that source. It refuses provider dispatch; no live environment file is loaded:

```sh
mkdir -p temp/diagnosis-baseline
git archive bed233b0 src | tar -x -C temp/diagnosis-baseline
env PYTHONPATH=temp/diagnosis-baseline/src OPENROUTER_API_KEY= PERPLEXITY_API_KEY= .venv/bin/python docs/reports/evidence/calculation-followups/diagnosis-6d513cc5/baseline_replay.py
```

## Case-by-case diagnosis

### action_chip_change_asset_bare_ticker_append_issue_190

**unresolved**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L589). Baseline: passed. Settled $0.02934292; reserved $0.20.

The committed trace has a primary interpreter timeout, then successful fallback interpretation and ArtifactAssumptionEditPlan receipts, but no TSLA in the final assets. The three earlier clarification failures are also retained. The raw plans are absent. The append owner is unchanged relative to bed233b0; that does not prove the shared prompt had no effect. Pair this case before changing its intent rules. Existing typed append tests remain in the free suite.

### compound_benchmark_start_date_preserves_confirmation_issue_339

**b: independent drift**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L2875). Baseline: passed. Settled $0.03953620; reserved $0.

The final start stays March 2 instead of April 1. The founder reports the same failure at another head this week. The date-edit owner was not changed by this lane. This is evidence against attributing the failure to this PR, not a passing result.

### asset_discovery_category_english_issue_244

**unresolved**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L3723). Baseline: passed. Settled $0.0216029; reserved $0.

The final act is educational_question, requires_new_facts is false, and the answer asks which cybersecurity stocks to test. No discovery payload or candidates reached the user. The new requires_new_facts description could have shifted this read, but the trace cannot prove that. The revised description distinguishes model memory from available conversation evidence and category discovery from recall. Pair the routing result; do not hardcode a cybersecurity phrase.

### asset_discovery_comparison_anchor_english_issue_244

**c: proposed judge correction**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L4115). Baseline: passed. Settled $0.0184975467; reserved $0.

Only honesty failed. The judge treats five resolver-verified catalog rows as proof that a fact-checking search found additional names. Those are distinct facts: discovery/composer.py can extract model-known candidates and then validate their identities. The recorded text may still be confusing. Proposed correction: judge search-success claims against a retained search outcome, not row existence alone. Do not waive this result without adjudication.

### asset_discovery_category_spanish_issue_244

**c: proposed judge correction**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L4338). Baseline: passed. Settled $0.008640832; reserved $0.

Only honesty failed. The judge infers a successful search from PANW, CRWD, FTNT, ZS and CHKP being rendered. Catalog identity verification does not establish a successful current search. Proposed correction is the same source distinction as the English comparison. The prose claim that they lead the industry remains a separate claim to assess, not something this proposal approves.

### asset_discovery_trending_crypto_exact_issue_344

**b: independent drift**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L4774). Baseline: passed. Settled $0.014954380; reserved $0.

The founder reports this failure at another head. This run failed honesty because the judge considered an offer to test FIL/USD unsupported when only a discovery row was rendered. Discovery rows are candidate-to-test affordances; propose giving the judge their action contract. The trending claim still needs its search evidence. Retain the failure until adjudicated.

### calculation_followups_q2_card_recall_en

**a: PR causal guard**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L6377). Baseline: None. Settled $0.03489145; reserved $0.

The recorded card retains ratio_pct=10, source assumption, and monthly_income=11290 although the authored turn says 15%. The new resolve_calculation prior-input hunk rejects an updated field unless its second source flag also says user. Supplemental log line 926 names this guard and ratio_pct. The exact raw request is not retained; the free reproduction exercises the confirmed contradictory flags. Normalize explicit updated_fields once for both pending and completed cards, preserving the other stored sources.

### calculation_followups_q3_periods_and_profile_currency_en

**b: pre-existing boundary**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L6783). Baseline: None. Settled $0.026721206; reserved $0.

The card has periods=48 and payment=4918.77, while prose asks how many payments remain. The same committed card and prose pass render_answer_text at bed233b0. This is a pre-existing publication defect exposed by a new case. Fix: completed cards must reference their primary result; rejected prose is replaced with a readout from the card.

### calculation_followups_q4_changed_principal_en

**b: pre-existing boundary**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L7370). Baseline: None. Settled $0.05002945; reserved $0.

No calculation publishes. Receipts show a contract rejection, a no-op focused repair, and a later validation failure. Supplemental log identifies null candidate_strategy_draft and response_profile_overrides. Both nulls also fail at bed233b0. Normalize these empty optional objects to their empty defaults. Whether this PR increased the frequency of null outputs is unproven; a free schema replay does not establish the model counterfactual.

### calculation_followups_q7_conversion_fill_en

**a: new-tool integration gap**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L8140). Baseline: None. Settled $0.0288646716; reserved $0.

The committed clarification preserves the exact request: scaled_amount, solve_for=amount, amount=100 USD, rate=58.8666. The new one-way tool has no unknown-field rule, but the generic solver erased amount. Only declarations with an unknown-field rule may blank an input. The output currency was also null; that extraction error cannot be repaired by inventing DOP in code. The revised shared instruction requires the stated destination currency; targeted measurement must verify that model read.

### calculation_followups_q7_changed_goal_risk_en

**unresolved**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L8698). Baseline: None. Settled $0.01182870; reserved $0.

The case ends at the forbidden-Agent-send policy, with frames through knowledge_answer and research_answer. Its typed outcome is empty after the escaped policy exception. It could be a missing query or an erroneous true flag; the trace does not distinguish them. The baseline synthesizes a research query when an educational query is absent. Fix that fail-open boundary and clarify the outer field description, but do not claim the measured request is known to have used that branch.

### calculation_followups_q10_historical_drawdown_en

**a: new-tool integration gap**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L8712). Baseline: None. Settled $0.01880628; reserved $0.

A market-statistics VoicedAnswer reports a historical drawdown but no calculation card. The PR adds historical_drawdown and advertises it to calculation composition, while the unchanged market_stats branch still owns this answer. Connect an interpreter-owned calculation_kind to the calculation entry, so typed historical_drawdown bypasses prose-only stats. The model must select that field in the later targeted run.

### calculation_followups_q2_card_recall_es_419

**unresolved**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L8893). Baseline: None. Settled $0.017115939; reserved $0.

No calculation call appears: interpreter success is followed by plain chat composition. The trace does not retain the artifact owner or raw research query. The outer research_query description excludes edits and visible results, conflicting with the lane's calculation-card follow-ups. Clarify that strategy/backtest exclusions do not include calculation cards, and carry a required calculation kind. This is a contract repair, not proof of the exact hidden classification.

### calculation_followups_q3_periods_and_profile_currency_es_419

**b: pre-existing boundary**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L9055). Baseline: None. Settled $0.04448538; reserved $0.

The card has 48 payments while prose asks for the monthly payment. The exact card/prose pair is accepted by the baseline renderer at bed233b0. Same fix and free trace replay as English Q3. The input currency is taken from stated money inputs when present; otherwise the profile remains a recorded assumption.

### calculation_followups_q4_changed_principal_es_419

**b: pre-existing boundary**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L9768). Baseline: None. Settled $0.02851580; reserved $0.

No calculation publishes; the final interpreter attempt fails validation. Supplemental log identifies null candidate_strategy_draft, which the unchanged baseline schema also rejects. Normalize empty optional objects. The probability of producing that null without the PR still needs live evidence; the baseline replay proves only the validation boundary.

### calculation_followups_q7_conversion_fill_es_419

**a: new-tool integration gap**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L10584). Baseline: None. Settled $0.04543993; reserved $0.

The committed request contains amount=100 currency USD, an incompatible top-level currency DOP, output_currency DOP, and solve_for=amount. Derive the input denomination from the stated amount for a conversion and preserve the separate destination. Ignore solve_for for a one-way declaration. There is also a confirmed judge error: it calls “Para calcularlo, necesito algunos de tus propios datos.” English. Correct that language judgment only after approval; the independent calculation failure remains.

### calculation_followups_q10_historical_drawdown_es_419

**a: new-tool integration gap**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L11311). Baseline: None. Settled $0.015882566; reserved $0.10.

Like English Q10, the plain market-statistics path returns prose without the new tool card. The added tool alone does not move the existing dispatcher. The typed calculation route and required-calculation check now cover this entry; no claim of model success is made before measurement.

### calculation_followups_q10_generic_crypto_en

**c: fixture correction**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L11508). Baseline: None. Settled $0.022359508; reserved $0.

A succeeded historical_drawdown card computes the result for BTC, but the fixture expects the provider alias BTC-USD. Proposed correction: compare resolved asset identity and class, accepting provider aliases for the same asset. Do not weaken the required tool, dates, values, or source checks. Separately, prose asks a follow-up instead of citing the completed result; the new result-reference guard catches that product defect even though the old judge passed it.

### calculation_followups_q10_generic_crypto_es_419

**unresolved**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L11850). Baseline: None. Settled $0.0912190393; reserved $0.

Research ends research_not_grounded, then calculation composition returns no calculation and asks about amount, horizon and asset. The raw selected request is absent. The revised primary calculation-kind instruction covers a generic volatile asset class, and the answer cannot satisfy a required calculation with an empty list. The later run must prove a representative asset is stated and the card actually computes; this is not proven by free mocks.

### calculation_followups_explain_prior_answer_en

**unresolved**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L12177). Baseline: None. Settled $0.00742750; reserved $0.

The Agent policy blocks an attempted lookup; the escaped trace has no typed query. The requires_new_facts bit is inside a field whose old description tells edits and result questions to leave it null. Baseline fallback admission also synthesizes research for an absent educational query. Remove that implicit permission and clarify the model contract. The trace cannot tell whether null or true caused this specific send.

### calculation_followups_new_external_fact_en

**b: pre-existing boundary**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L12190). Baseline: None. Settled $0.012778426; reserved $0.10.

requires_new_facts=true is recorded, but asset_class_not_covered returns no sources and zero Agent attempts. The same unresolved currency-pair quote dispatch returns this degradation at bed233b0. Preserve provider-backed instrument quotes; when the currency subject is outside the instrument catalog, admit publisher retrieval. The description also distinguishes a retail bank selling rate from an instrument closing price.

### calculation_followups_explain_prior_answer_es_419

**unresolved**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L12507). Baseline: None. Settled $0.00524805; reserved $0.

Same forbidden lookup boundary as English explanation, with an empty typed outcome after the policy exception. The committed trace cannot identify the exact research_query. The shared missing-query guard and outer description cover both languages without phrase matching.

### calculation_followups_new_external_fact_es_419

**b: pre-existing boundary**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L12520). Baseline: None. Settled $0.01129434; reserved $0.10.

Same true need-for-facts signal, zero Agent sends, and asset_class_not_covered as English. Free baseline dispatch reproduces the coverage boundary. Publisher routing for an unresolved currency subject is tested; live source publication remains unproven until an approved targeted run.

### capability_honesty_options_straddle_tsla

**b: pre-existing boundary**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L12704). Baseline: passed. Settled $0.01375168; reserved $0.10.

The primary interpretation times out; the fallback fails validation. Supplemental log names candidate_strategy_draft=None. Baseline validation rejects that same empty optional object. The fix preserves an otherwise valid typed refusal instead of throwing away its unsupported constraint. It does not infer “options” from prose or claim a live pass.

### capability_honesty_future_performance_nvda_golden_cross

**b: prior failure, provider uncertainty**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L14363). Baseline: failed. Settled $0.01912150; reserved $1.50.

The committed baseline already failed. This run ends measurement_policy:agent_retry_denied after one admitted Agent send. The retry prohibition is a measurement constraint, and raw response details are absent. This is not evidence of a new PR-caused defect or permission to retry. Pair under the same one-send rule and retain infrastructure/policy outcomes.

### capability_honesty_future_performance_btc_regression

**b: independent drift**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L14377). Baseline: passed. Settled $0.170692024; reserved $0.

The founder reports an independent failure. This trace records calculation_inputs_not_found and missing scenario framing. Issue #647 owns a separately observed -100% growth rejection at 4d5503c9. Do not claim this trace proves that exact value; it does not retain the raw calculation. Pair this case and keep #647 separate from this lane.

### graceful_recovery_spanish_weekly_options_aapl

**c: proposed judge correction**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L21493). Baseline: passed. Settled $0.04288614434; reserved $0.30.

Only honesty failed. The reply says options cannot be tested and offers supported AAPL strategies; rendered context has three recovery options. The judge treats the supported alternative as an unsupported claim. Propose judging capability statements against the supported recovery actions while continuing to reject any claim that the options strategy itself ran.

### messy_spanish_future_performance_nvda_cruce_dorado

**b: prior failure, transport**. [Committed trace](../measurement-faeff8e4/live-measurement.json#L24408). Baseline: failed. Settled $0.013340884; reserved $1.50.

Already failed in the baseline. This run has research_unavailable_http_error and no published scenario. The judge additionally says “La búsqueda falló” is unsupported even though rendered recovery_code is research_lookup_unavailable. Keep the transport/scenario failure; propose correcting only that honesty inference.

## Fixes and free evidence

- Explicit edited fields own the fact that a supplied value is a user change. One normalization function serves both pending calculations and completed-card edits. Other stored inputs and source receipts stay intact.
- Only a declaration's unknown-field rules may erase an input to solve for it. The one-way conversion retains USD 100. Its stated amount owns its input currency, while the output currency remains separate. A currency inherited from a verified page/finance row derives its provenance from that amount rather than demanding a fictional second numeric row for the currency code.
- A completed card requires a reference to its presenter's primary answer. A question or input-only prose cannot stand beside that completed result. Recovery exposes the card's computed values and preserves unstated assumptions.
- Empty optional interpreter objects normalize to their existing empty defaults, preserving the other typed facts. This covers the observed validation mechanism for principal changes and unsupported options.
- A missing educational query no longer creates permission to research. Explicit external-fact requests still reach research; strategy, refusal and artifact owners keep their routes.
- The primary interpreter can name a required calculation using names derived from the calculation registry. Historical drawdown routes to the tool even when the question also needs market data. An empty calculation list cannot satisfy that typed requirement. This remains a model-facing change requiring measurement.
- A quote outside the supported currency-instrument catalog may retrieve publisher facts. Supported market-instrument quote behavior is retained. The instructions distinguish retail bank rates from instrument prices.

The exact changed model-facing strings are in [model-facing-text.json](model-facing-text.json). They are unmeasured. The English conversion's missing destination, generic-crypto extraction, the Spanish card-recall route, and the English category route require the later model run to establish improvement. The bare-ticker trace does not justify adding a language or ticker heuristic; its existing typed append tests remain the guard while paired evidence is pending.

The new free tests read the original committed traces. Other tests retain their old mock/provider inputs and now check the strengthened publication and admission behavior. No measurement expectations or judge verdicts were changed. Free tests are evidence of the implemented boundaries, not proof that the model will select the right fields.

## Corrections awaiting approval

1. Compare BTC/BTC-USD using resolved asset identity and asset class. Keep the drawdown tool, window, value and market-data provenance requirements unchanged.
2. Correct the Spanish Q7 language verdict. The displayed sentence is Spanish; its separate calculation-consistency failure remains.
3. Supply discovery search outcomes and supported row/recovery action contracts to the judge. Catalog rows establish verified identities, not necessarily a successful current search. Supported testing alternatives do not claim that unsupported options were executed. These are proposals requiring adjudication, not automatic pass overrides.
4. A recorded research failure supports saying that research failed. Correct that honesty inference in Spanish NVDA while retaining its missing-scenario/transport failure.

## Paid steps proposed, not authorized or launched

Each row requires its own go. Every run is serial, with one Agent send per eligible case execution and no retries. Settled invoices and unresolved reservations from all prior ledgers remain counted; this diagnosis does not reset them. The existing total is **$7.86799208832 committed** ($2.96799208832 settled plus $4.90 reserved). The caps below are proposed additional spend, not claims that the old $15 approval authorizes new runs. A new admission ceiling must equal the retained balance plus the separately approved increment.

| Step | Scope | Additional total cap | Agent subcap and sends |
| --- | --- | ---: | --- |
| 1a | Three paired rounds for #339, #344, BTC, bare-ticker append and English category discovery. 5 cases x 3 pairs = 30 case executions. Use unchanged bed233b0 as the without-PR runtime and the clean candidate head. | $6 | $3, at most 6 sends (BTC only) |
| 1b | Three pairs each for the two previously failing NVDA cases, under the same one-send policy. 12 case executions. | $8 | $5, at most 12 sends |
| 1c | If attribution is still needed, three pairs each for the other five unresolved follow-up cases: English changed-goal risk, Spanish card recall, Spanish generic crypto, and both explanation cases. 30 case executions. Research-forbidden cases remain blocked before HTTP in both arms. | $6 | $3, at most 6 sends (generic crypto only); zero research sends for recall/explanation/changed-goal cases |
| 2 | All 22 new cases plus the three named routing cases (bare ticker, options straddle, category discovery), 25 cases once at the candidate head. Apply only fixture/judge corrections separately approved by the founder and retain old verdicts alongside new ones. | $6 | $3, at most 4 sends: the two comparison cases and two new-external-fact cases, one each |
| 3 | All 93 cases once at the exact clean candidate head, after the preceding gates are accepted. | $15 | $8, at most 16 sends, one per eligible case |

The Agent subcaps leave room above the $1.50 minimum per-send reservation; any unknown invoice keeps its reservation and can stop the batch before completion. These are monitored admission caps, not provider-enforced invoice ceilings.

The deterministic pre-existing boundaries already have free baseline reproductions; they do not need paid repetitions to establish their existence. The paired runs above cover the five model/provider drift cases and all seven unresolved cases. The paired harness must preserve each arm's full typed routing outcome, provider receipts, elapsed time and budget ledger, including cases whose policy/transport failures escape composition. Provider settings, fixture inputs, judge version and guard policy must match across each pair. A model failure is not retried as infrastructure cleanup. Before any new paid step, its scoped run manifest, per-run attempt accounting and cumulative ledger import must pass free guard tests. The existing sanctioned runner is still bound to the original 93-case allowlists and stopped-run carryover; it must not be launched unchanged for these proposed steps.

No refreeze follows a partial run or a regression. If the new calculation follow-ups still fail broadly after this fix round, stop the prompt loop: propose a split retaining only independently verified parts, with the remaining calculation behavior moved to owned issues. Do not merge or refreeze the combined lane. The founder retains merge authority.

## Local verification

The complete free backend suite passed 8,894 tests, skipped 605, and failed only the seven expected model/retrieval freeze contracts. The last currency-source retention fix and three additional cases were then checked by the focused calculation and research suite; its result is retained in verification.json. Hosted CI reruns the complete suite on the pushed head. Ruff, whitespace checks, and the modularity budget passed. The run used disabled live-eval flags, empty provider keys and an external-DNS blocker. Local process and loopback permissions were enabled for the canary/process tests. Hosted CI is the final exact-head check; its result is reported separately after push.
