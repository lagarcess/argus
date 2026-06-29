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

- Added non-headline execution realism metadata showing gross vs net return.
- Result card assumptions now say the modeled costs and their effect, for
  example: `Modeled 10 bps fee + 5 bps slippage; net +11.8% vs gross +12.0%.`
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
