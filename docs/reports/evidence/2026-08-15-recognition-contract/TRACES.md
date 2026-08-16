# Recognition contract: live end-to-end fact-drop traces

Instrumented live-spine probes at base `584e9a01` (merge of #515), captured
2026-08-15 with live provider modes (`live_provider` market data + asset
catalog, real OpenRouter interpretation). The probe hooks the interpret
pipeline at six seams and records the full typed object at each one, so a
typed fact's disappearance names the exact layer that discarded it. Probe:
`temp/probe_recognition_trace.py` (session artifact); raw seam dumps sit
beside this file under `traces/`.

The lane's question: when Argus answers an editing or capability-limit turn
as chat and forgets the user's facts, does the interpreter drop the facts, or
does a later layer overwrite a correct read? Answer, on every traced failure:
**the model's read was correct — in one case three independent model reads
were correct — and a post-read layer destroyed it.** This is the same defect
class #515 proved on the discovery surface (`research_decision()` rebuilding
a typed decision with a hardcoded act), now traced at four more sites.

## Trace 1: "remove AAPL" (editing class, six eval failures)

Case `action_chip_change_asset_remove_aapl_issue_188`: a `change_asset` chip
clarifies, the user replies "remove AAPL" against a pending
AAPL+MSFT+NVDA confirmation. Failing signature: `intent:
conversation_followup` (expected `backtest_execution`), AAPL retained,
turn ends `ready_to_respond`.

What the failing trace (`traces/remove_aapl_fail.json`, attempt c) shows:

1. **Raw model read is perfect.** `intent=strategy_drafting`,
   `semantic_turn_act=refine_current_idea`, and the typed role-separated
   edit contract exactly as the schema requests it:
   `asset_exclusions=["AAPL"]`, `asset_universe_operation="replace"`,
   `field_provenance={"asset_exclusions": "explicit_user"}`,
   `evidence_spans={"asset_exclusions": "remove AAPL"}`, and
   `asset_universe=[]` (the schema says not to copy carried assets).
2. **Normalization manufactures a contradiction.**
   `response_with_provider_context_assets`
   ([provider_context_assets.py:148-149](../../../../src/argus/agent_runtime/interpreter/provider_context_assets.py))
   overwrites `draft.asset_universe` with the mention-extraction rows. The
   only mention in "remove AAPL" is AAPL, so the asset the user excluded is
   injected as the traded set: `asset_universe=["AAPL"]`,
   `asset_exclusions=["AAPL"]`. The injection never consults
   `asset_exclusions`.
3. **The planner gate now demands a planned edit.** With a non-empty
   universe differing from the card,
   `_active_artifact_asset_universe_operation_needs_planner`
   ([readiness_helpers.py:35-75](../../../../src/argus/agent_runtime/interpreter/readiness_helpers.py))
   routes the turn to the artifact edit planner
   ([llm_interpreter.py:2793](../../../../src/argus/agent_runtime/llm_interpreter.py)).
4. **Two more model reads are perfect.** Both planner models return
   `outcome=ready_to_confirm`,
   `operations=[{op: remove, target: asset, symbols: [AAPL]}]` — grok and
   haiku agree, and `_has_supported_edit` accepts the plan.
5. **A deterministic coherence check kills both correct plans.**
   `materialized_artifact_edit_targets` returns `None` for each plan because
   `primary_assets & primary_asset_exclusions` is non-empty
   ([artifact_assumption_edit.py:941-948](../../../../src/argus/agent_runtime/interpreter/artifact_assumption_edit.py))
   — the very overlap that step 2 manufactured. `_covers_required_targets`
   ([artifact_edit_planner.py:220-225](../../../../src/argus/agent_runtime/artifact_edit_planner.py))
   then refuses every plan and the planner returns `None`.
6. **The fallback erases the typed facts.**
   `_asset_universe_operation_clarification_response`
   ([readiness_helpers.py:78-109](../../../../src/argus/agent_runtime/interpreter/readiness_helpers.py),
   fired from
   [llm_interpreter.py:2800](../../../../src/argus/agent_runtime/llm_interpreter.py))
   rebuilds the turn: `intent=conversation_followup`,
   `semantic_turn_act=answer_pending_need`, the draft wiped of every asset
   fact (only `position_size` survives by design), and a canned question —
   "Do you want to add those assets to the current strategy, or replace the
   current assets with them?" — that does not even offer *remove*, the
   operation three model reads had already typed. Reason code
   `asset_universe_operation_needs_clarification` is recorded, so the layer
   is observable, but the typed exclusion facts are gone.
7. The turn ends `ready_to_respond` as chat; AAPL is retained.

The passing attempt (`traces/remove_aapl_pass.json`) shows why the case
flips by serving day: it passes only when the model *disobeys* the
role-separation instruction and does the subtraction itself
(`asset_universe=["MSFT","NVDA"]` plus the exclusions). The pipeline
punishes the schema-correct read and survives on the schema-incorrect one.
That is the recognition defect in its purest form: the deterministic layers
only accept the shape the schema tells the model not to produce.

## Trace 2: weekly options (capability-limit class, two eval failures)

Case `graceful_recovery_weekly_options_aapl`: "please backtest weekly
options on apple from 2024-01-01 through 2024-12-31". Failing signature:
`intent: conversation_followup`, `assets: []`, no date range, no benchmark,
turn ends `ready_to_respond`.

What the failing trace (`traces/weekly_options_fail.json`) shows:

1. **Raw model read is perfect.** `intent=unsupported_or_out_of_scope`,
   `semantic_turn_act=unsupported_request`, `asset_universe=["AAPL"]`,
   `date_range={2024-01-01..2024-12-31}` with evidence spans, and a typed
   `unsupported_constraints` payload: category `strategy_type`, raw value
   "weekly options", a plain-language explanation, and
   `simplification_options` including **"Buy and hold AAPL over the same
   dates"** — the exact never-stall / name-the-limit / keep-every-fact /
   offer-the-nearest-thing answer the product rule demands, already typed.
2. **The audits enrich it further**: provider-resolved AAPL,
   `asset_class=equity`, default benchmark SPY
   (`unsupported_request_default_benchmark_applied`).
3. **The knowledge/research rail claims the turn.**
   `knowledge_answer_stage_result` runs before routing
   ([interpret.py:422-427](../../../../src/argus/agent_runtime/stages/interpret.py)).
   `unsupported_request` is a knowledge-shaped act by definition
   ([knowledge_answer.py:52-56](../../../../src/argus/agent_runtime/knowledge_answer.py)),
   and the draft's AAPL + dates are reference fields that do not count as
   execution evidence
   ([draft_shape.py:471-482](../../../../src/argus/agent_runtime/interpreter/draft_shape.py)),
   so no veto applies. With the research rail enabled,
   `research_answer_stage_result`
   ([research_answer.py:98-111](../../../../src/argus/agent_runtime/research_answer.py))
   re-classifies **the raw message only** — nothing consults the primary
   read's typed `unsupported_request` verdict or its constraint payload —
   and the classifier types "please backtest weekly options…" as
   `market_stats`.
4. **A stats answer replaces the recovery.** The turn ends
   `ready_to_respond` with a year of AAPL price statistics
   (`knowledge_answer_market_stats`). The typed constraint, the
   simplification options, the asset, the window, and the benchmark are all
   discarded. The user asked to run something; Argus answered a question
   they never asked and forgot everything they said.

This is byte-for-byte the #515 mechanism: a message-only sidecar classifier
overriding a typed primary decision, and the diversion erasing the typed
payload. #515 closed it for `asset_discovery` payloads; the
`unsupported_constraints` payload has the identical hole.

## Trace 3: DCA $0 contribution (verdict ignores typed facts)

Case `dca_capital_semantics_zero_contribution_names_buy_and_hold_issue_455`:
"$5,000 to start and $0 added each month" should reach the launch validator
and be named `dca_contribution_zero_is_buy_and_hold`. Failing signature:
verdict `unsupported`, no validation code.

What the failing trace (`traces/dca_zero_contribution_fail.json`) shows:

1. **Raw model read types the seed correctly**: `initial_capital=5000.0`
   with `field_provenance={"initial_capital": "starting_capital"}` and
   evidence span "$5,000 to start".
2. **A sidecar audit overrides the primary's typed role.** The
   `DcaContributionRoleAudit` sidecar concludes `total_budget_not_recurring`
   and `_move_dca_total_budget_out_of_recurring_amount` re-types the money:
   after audits the draft carries `total_capital=5000` — the user's
   explicitly-provenance-tagged *seed* has become a *budget*
   ([llm_interpreter.py:2151-2174](../../../../src/argus/agent_runtime/llm_interpreter.py),
   reason code `dca_total_budget_role_audited`). No tiebreak rule prefers
   the primary's explicit `starting_capital` provenance over the sidecar's
   contrary read, and the recorded reason code says the audit fired, not
   that it contradicted an explicit provenance fact.
3. **Semantic integrity turns the fabricated budget into a refusal.**
   `conserve_semantic_constraints` reads `total_capital` as a contribution
   ceiling and emits `unsupported_dca_contribution_ceiling` — "I understand
   $5,000 as a total budget…" — a reading the user never stated
   ([semantic_integrity.py:143-152](../../../../src/argus/agent_runtime/semantic_integrity.py)).
   The turn ends `needs_clarification`/`unsupported` and the zero-contribution
   buy-and-hold rule is never reached.

## Trace 4: DCA ceiling (receipted deferral, not a silent drop)

Case `dca_capital_semantics_only_have_amount_is_ceiling_issue_455`:
"I only have $5,000 … every month". In today's failing attempt
(`traces/dca_ceiling_fail.json`) the pipeline behaves differently from the
other three: the model types `total_capital=5000` (explicit_user) and
`missing_required_fields=["capital_amount"]`, semantic integrity produces
the full typed `unsupported_dca_contribution_ceiling` constraint **with all
three simplification options**, and the interpret patch carries everything.
The clarify stage then deliberately strips the ceiling constraint while DCA
execution details are missing
([clarify.py:669-694](../../../../src/argus/agent_runtime/stages/clarify.py))
and asks a generic `missing_sizing_amount` question — so the user who just
said "$5,000" is asked for an amount with no acknowledgment that their
$5,000 was heard. The deferral is receipted
(`semantic_dca_contribution_ceiling_deferred`), so this is a deliberate
product decision colliding with the eval expectation rather than a silent
drop; it is documented here because its user-visible effect is the same.
(The run-2 failing signature for this case — `missing_required_fields`
empty — is a different serving-day mode not reproduced today.)

## The class, named

Every traced failure has one shape: **a layer downstream of the primary
interpretation rebuilds the turn from its own narrower read and discards
typed facts the primary produced.** The overriding layer is sometimes
deterministic (context asset injection, the materializer coherence check,
the canned operation clarification, the clarify deferral) and sometimes a
sidecar model read (the rail classifier, the DCA role audit); in no case
does it check whether the primary read already answered its question, and
in no case does the typed fact survive the rebuild. #515's fix — route on
the typed payload, keep the typed decision across diversions, record every
deterministic override — is the proven shape for closing this class.

## Cost

Seven probe attempts (3 editing, 1 weekly options, 3 DCA), each a full
interpret-stage turn with audits: ≈$0.35 total.
