# Execution Realism Summary

Issue #130 was implemented on `codex/engine-realism` in four phase commits. The
feature is still gated by `ARGUS_ENABLE_EXECUTION_REALISM`; when the flag is off,
the engine strips `_execution_realism` and the config, metrics, chart, and result
card remain byte-identical to the pre-feature path.

## Phase 1 - Launch Payload Plumbing

- Added opt-in launch payload plumbing from drafted strategy
  `extra_parameters.fee_rate` / `extra_parameters.slippage` decimal values to
  `_execution_realism.fee_bps` / `_execution_realism.slippage_bps`.
- Extended the launch request model and adapter so flagged payloads reach the
  engine config without changing unflagged requests.
- Proof:
  `tests/agent_runtime/test_execute_launch_payload.py::test_launch_payload_maps_decimal_execution_realism_to_bps_when_flag_on`,
  `tests/agent_runtime/test_execute_launch_payload.py::test_launch_payload_omits_execution_realism_when_flag_off`,
  and
  `tests/domain/test_engine_launch.py::test_launch_adapter_propagates_execution_realism_to_engine_config_when_flag_on`.

## Phase 2 - Engine Math

- Applied fee and slippage costs to long-only buy-and-hold, signal strategies,
  and DCA fills through the existing engine path.
- DCA now buys fewer shares per contribution when modeled costs are enabled, so
  repeated fills carry repeated cost impact instead of a single headline drag.
- Metrics-path rule: when no costs are modeled (flag off, or flag on with zero
  fee and slippage) the engine keeps the legacy returns-based
  `_compute_metrics` float path bit-for-bit; the equity-based
  `_compute_metrics_from_equity` path runs only when costs are modeled, because
  a pct_change return series cannot see the entry-cost hit at t0. An earlier
  draft of this phase swapped the shared path unconditionally, which flipped
  rounded output on exact rounding ties (1.875% -> 1.88 instead of the legacy
  1.87); the tie-boundary regression test below pins the legacy behavior.
- Golden-number proof: the existing flag-off buy-and-hold fixture still asserts
  +12.0% total return, +6.0% benchmark return, +6.0% delta, and about $1,200
  profit; the existing flag-off DCA fixture still asserts about $40.68 profit.
- Proof:
  `tests/section3/test_engine_simulation.py::test_buy_and_hold_execution_realism_reduces_net_return_and_profit`,
  `tests/section3/test_engine_simulation.py::test_signal_strategy_execution_realism_reduces_net_return_and_profit`,
  `tests/section3/test_engine_simulation.py::test_dca_execution_realism_reduces_net_return_and_profit`,
  and
  `tests/section3/test_engine_simulation.py::test_flag_off_total_return_keeps_legacy_rounding_at_tie_boundary`.

## Phase 3 - User-Facing Trust Surface

- Added structured execution realism metadata showing gross return, net return,
  return drag, and same-cost benchmark treatment.
- Result card assumptions now keep one concise cost line, for example:
  `Net of 10 bps fee + 5 bps slippage.`
- Confirmation surfaces render nonzero modeled costs from the launch payload or
  drafted strategy, without inventing costs when the feature is off.
- Proof:
  `tests/section3/test_engine_simulation.py::test_build_result_card_shows_execution_realism_cost_and_effect`,
  `tests/test_runtime_confirmation_card.py::test_runtime_confirmation_card_shows_execution_realism_values`,
  `web/__tests__/confirmation-assumptions-display.test.ts`, and
  `web/__tests__/result-card-playground.test.ts`.

## Phase 4 - Benchmark Parity And Acceptance Proof

- Chosen benchmark decision: benchmarks use the same modeled fees and slippage
  when execution realism is enabled, so delta compares net strategy performance
  against a net benchmark on the same cost assumptions.
- Result card assumptions explicitly mark that parity:
  `Benchmark: SPY (same modeled costs)`.
- Added final acceptance proofs for flag-off byte identity, DCA fill-count cost
  sensitivity, and multi-symbol aggregation without double-counting costs. The
  byte-identity test is parameterized across buy-and-hold, DCA, and
  signal-strategy templates, including multi-symbol runs.
- Proof:
  `tests/section3/test_engine_simulation.py::test_execution_realism_flag_off_is_byte_identical`,
  `tests/section3/test_engine_simulation.py::test_dca_execution_realism_drag_increases_with_more_fills`,
  and
  `tests/section3/test_engine_simulation.py::test_multi_symbol_execution_costs_are_not_double_counted`.

## Phase 5 - Editable Costs On The Confirmation Card

- The confirmation card now carries backend capability truth: when
  `ARGUS_ENABLE_EXECUTION_REALISM` is on, the card payload includes
  `capabilities.execution_costs_editable: true`; with the flag off the field is
  absent and the card renders exactly as today.
- The assumptions band shows the current fee/slippage truth (already present)
  and, when the capability is on, adds an "Edit costs" chip that opens a small
  inline editor. Inputs are percent-per-trade, validated non-negative (slippage
  capped at the declared 5% capability range). Applying composes the canonical
  natural-language edit ("Set fees to X% and slippage to Y% per trade.") and
  sends it through the existing `adjust_assumptions` action flow, so both the
  chip and free-typed edits converge on the existing typed fees/slippage edit
  operations. No changes to `artifact_edit_planner.py` or the interpreter.
- Capability gates opened for the flag-on path only: the confirm stage no
  longer bounces nonzero fees/slippage as unsupported when the engine flag is
  on (flag off keeps today's bounce), and the launch payload now also reads
  fees/slippage from resolved optional parameters when the draft has none.
  Negative values are never modeled.
- Default remains no fees and no slippage; costs are user opt-in per idea.
- Proof:
  `tests/agent_runtime/test_conversation_stages.py::test_confirm_stage_accepts_nonzero_costs_when_execution_realism_enabled`,
  `tests/agent_runtime/test_execute_launch_payload.py::test_launch_payload_reads_execution_realism_from_optional_parameters`,
  `tests/agent_runtime/test_execute_launch_payload.py::test_launch_payload_ignores_negative_execution_cost_values`,
  `tests/test_runtime_confirmation_card.py::test_runtime_confirmation_card_flag_on_marks_execution_costs_editable`,
  `tests/test_runtime_confirmation_card.py::test_runtime_confirmation_card_flag_off_omits_capabilities`,
  and `web/__tests__/confirmation-cost-edit.test.ts`.

## Phase 6 - Result Card Cost Evidence

- The result card always carries one honest assumption line: idealized runs
  keep "No fees/slippage" and cost-modeled runs keep a concise "Net of..."
  modeled-cost line. Gross/net and drag live in structured details.
- The backend result card payload now includes a structured
  `execution_costs` block (`fee_bps`, `slippage_bps`, `gross_total_return_pct`,
  `net_total_return_pct`, `return_drag_pct`,
  `benchmark_treatment: "same_modeled_costs"`) only when the engine modeled
  non-zero costs. Idealized cards are byte-identical to before.
- The view-details pane renders a cost section from that structured payload —
  Gross return, Net of costs, Costs modeled, and the benchmark cost treatment —
  never parsed from prose and never invented client-side. Cards without the
  block render exactly as today, including old persisted cards.
- Proof:
  `tests/section3/test_engine_simulation.py::test_build_result_card_shows_execution_realism_cost_and_effect`,
  `tests/section3/test_engine_simulation.py::test_build_result_card_omits_execution_costs_without_modeled_costs`,
  and the `web/__tests__/result-card-playground.test.ts` cost-evidence tests.

## Cold-Start Cost Capture

- The interpreter system prompt previously declared "no real slippage/fee
  realism," so explicit costs in a user's first message were dropped from the
  draft. The capability clause is now flag-aware
  (`interpreter/execution_cost_capability.py`): with the flag off it keeps the
  legacy sentence byte-for-byte; with the flag on it states that per-trade fee
  and slippage assumptions are supported and instructs the interpreter to
  record explicit values, in any language, as decimal fractions in
  `extra_parameters.fee_rate` / `extra_parameters.slippage` with
  `explicit_user` provenance. No regex or language gates; extraction stays
  LLM-owned with deterministic validation after.
- Proof:
  `tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py::test_llm_system_prompt_keeps_legacy_cost_capability_when_flag_off`,
  `tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py::test_llm_system_prompt_instructs_cost_capture_when_flag_on`,
  `tests/agent_runtime/test_interpret_stage.py::test_cold_start_explicit_costs_flow_to_launch_payload_when_flag_on`,
  `tests/agent_runtime/test_interpret_stage.py::test_cold_start_explicit_costs_stay_inert_when_flag_off`,
  and the deterministic reroute-predicate tests in
  `tests/agent_runtime/test_refine_action_edit_routing.py`.
- Live QA (dev backend, flag on): English and Spanish cold-start messages with
  "0.1% fees and 0.05% slippage" produced a first confirmation card reading
  `Modeled costs: 10 bps fee + 5 bps slippage` /
  `Costos modelados: comisión de 10 bps + deslizamiento de 5 bps`; running it
  produced the net result card (gross -14.8% vs net -14.9%), and a follow-up
  "what fees did this include?" was answered from the structured cost facts.

## Cross-Commit Byte-Identity Audit

Beyond the in-suite tests (which compare HEAD to HEAD), the flag-off prime
directive was verified cross-commit: the full engine output (normalized
config, aggregate + per-symbol metrics, chart, result card in en and es) was
serialized at full float precision for a matrix of buy-and-hold, DCA, and
signal strategies (single and multi-symbol, equity and crypto, 7-bar and
120-bar fixtures) and byte-compared against the pre-lane baseline commit and
against the `codex/private-alpha-next` base after rebase. Output is
byte-identical with the flag off, and also with the flag on when fee and
slippage are zero.

## Blockers

None.
